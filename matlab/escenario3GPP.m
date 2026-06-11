% Script de MATLAB: Simulación Multi-Celda RSRP 3GPP TR 38.901 con GeoTIFF
% Diseñado para validación cruzada con implementaciones en Python

%% 1. Configuración del Entorno y Parámetros Globales
clc; clear; close all;

% Parámetros de diseño (Iguales a tu configuración Python: use_dem=False, scenario='UMa')
freq = 3500e6;          % 3500 MHz
txPower_dBm = 38;       % Potencia Tx: 38 dBm
txGain_dBi = 15;        % Ganancia máxima de la antena direccional
txHeight = 25;          % Altura BS: 25 m
rxHeight = 1.5;         % Altura UE: 1.5 m

% Parámetros de la Antena Direccional (Patrón estándar 3GPP / Atoll)
horizontal_HPBW = 65;   % Ancho de haz a -3dB (Half Power Beamwidth) en grados
max_attenuation = 30;   % Atenuación máxima hacia atrás (Front-to-Back ratio en dB)

%% 2. Definición de las 3 Antenas (Ejemplo de posiciones)
% Define aquí las coordenadas reales de tus 3 antenas
txLats = [-2.897974, -2.897974, -2.897974]; 
txLons = [-79.004898, -79.004898, -79.004898];
txAzimuths = [0, 120, 240]; % Ángulo de apuntamiento de cada antena (grados)

numAntenas = length(txLats);

%% 3. Cálculo del Centro Común y Generación de la Grilla (Resolución 20m)
centerLat = mean(txLats);
centerLon = mean(txLons);

% Crear grilla en metros (-3000m a +3000m para cubrir 3km a la redonda)
resolucion_m = 20; 
rango_m = -3000:resolucion_m:3000; 
[X, Y] = meshgrid(rango_m, rango_m);

% Dimensiones de la grilla (301 x 301 = 90,601 puntos)
[filas, columnas] = size(X);
numPuntos = filas * columnas;

% Proyección rápida y exacta de Metros a Lat/Lon usando el elipsoide WGS84
wgs84 = wgs84Ellipsoid("meters");
latVec = centerLat + (Y(:) / 111132); 
lonVec = centerLon + (X(:) / (111132 * cosd(centerLat)));

fprintf('Grilla generada: %d x %d = %d puntos (Resolución: %d m)\n', ...
    filas, columnas, numPuntos, resolucion_m);

%% 4. Inicialización de Matrices de Resultados
rsrp_matrix = zeros(numPuntos, numAntenas);
los_matrix = zeros(numPuntos, numAntenas);
pathloss_matrix = zeros(numPuntos, numAntenas);

%% 5. Bucle de Simulación por Antena
% Opción A: modelo estadístico puro 3GPP TR 38.901 (comparable con Python use_dem=False)
% LOS/NLOS determinado por probabilidad estadística Tabla 7.4.2-1, NO por trazado de rayos.
% nrPathLoss se llama dos veces (LOS forzado y NLOS forzado) y se mezcla con P_LOS(d).
plCfg = nrPathLossConfig;
plCfg.Scenario = "UMa"; % Urban Macro — mismo que Python scenario='UMa'

% Coordenadas de los Receptores (UEs) para el motor matemático
% El eje X de ue_coords = distancia 2D horizontal; nrPathLoss calcula d3D internamente.
ue_coords_base = [zeros(1, numPuntos); zeros(1, numPuntos); repmat(rxHeight, 1, numPuntos)];

% Vectores booleanos fijos para forzar LOS/NLOS en nrPathLoss
los_forced_true  = true(1, numPuntos);
los_forced_false = false(1, numPuntos);

for i = 1:numAntenas
    fprintf('Procesando Antena %d/%d (Azimuth: %d°)...\n', i, numAntenas, txAzimuths(i));
    
    % 1. Distancias 2D geodésicas [m] y azimuts desde esta antena
    d2D = distance(txLats(i), txLons(i), latVec, lonVec, wgs84);   % (numPuntos x 1)
    azToRx = azimuth(txLats(i), txLons(i), latVec, lonVec, wgs84); % (numPuntos x 1)
    
    % 2. Probabilidad LOS estadística — TR 38.901 Tabla 7.4.2-1 (UMa)
    % P_LOS(d) = min(18/d, 1) * (1 - exp(-d/63)) + exp(-d/63)
    d2D_safe = max(d2D, 1);                                          % evitar div/0
    exp_term = exp(-d2D_safe / 63);
    p_los = min(18 ./ d2D_safe, 1) .* (1 - exp_term) + exp_term;   % (numPuntos x 1)
    
    % 3. Patrón de radiación horizontal direccional — 3GPP TR 38.901 §7.3.2
    relAz = mod(azToRx - txAzimuths(i), 360);
    relAz(relAz > 180) = relAz(relAz > 180) - 360; % rango [-180, 180]
    antLoss = min(12 * (relAz / horizontal_HPBW).^2, max_attenuation); % (numPuntos x 1)
    
    % 4. Coordenadas cartesianas para nrPathLoss (d2D en eje X)
    bs_coords = [0; 0; txHeight];
    ue_coords = ue_coords_base;
    ue_coords(1, :) = d2D';   % (3 x numPuntos)
    
    % 5. Path loss LOS puro y NLOS puro — mismo nrPathLoss, solo cambia el flag LOS
    pl_los_vals  = nrPathLoss(plCfg, freq, los_forced_true,  bs_coords, ue_coords); % (1 x numPuntos)
    pl_nlos_vals = nrPathLoss(plCfg, freq, los_forced_false, bs_coords, ue_coords); % (1 x numPuntos)
    
    % 6. Mezcla estadística — E[PL] = P_LOS·PL_LOS + (1-P_LOS)·PL_NLOS
    % Equivalente exacto a Python: p_los * pl_los + (1 - p_los) * pl_nlos
    pl = p_los .* pl_los_vals' + (1 - p_los) .* pl_nlos_vals';     % (numPuntos x 1)
    pathloss_matrix(:, i) = pl;
    
    % Guardar probabilidad LOS en lugar de estado binario
    los_matrix(:, i) = p_los;
    
    % 7. RSRP = Ptx + Gtx - Pérdidas_Antena - PathLoss
    rsrp_matrix(:, i) = txPower_dBm + txGain_dBi - antLoss - pl;
end

%% 6. Procesamiento de Cobertura Agregada (Best Server)
% Encontrar el valor máximo de RSRP entre las 3 antenas para cada punto
[max_rsrp, best_antenna_idx] = max(rsrp_matrix, [], 2);

%% 7. Exportación Consolidada para Python
disp('Exportando grilla de datos a CSV...');

ResultadosExport = table(...
    X(:), Y(:), latVec, lonVec, ...
    rsrp_matrix(:,1), rsrp_matrix(:,2), rsrp_matrix(:,3), max_rsrp, ...
    pathloss_matrix(:,1), pathloss_matrix(:,2), pathloss_matrix(:,3), ...
    los_matrix(:,1), los_matrix(:,2), los_matrix(:,3), ...
    best_antenna_idx, ...
    'VariableNames', {...
    'X_m', 'Y_m', 'Latitud', 'Longitud', ...
    'RSRP_Ant1_dBm', 'RSRP_Ant2_dBm', 'RSRP_Ant3_dBm', 'RSRP_Max_dBm', ...
    'PathLoss_Ant1_dB', 'PathLoss_Ant2_dB', 'PathLoss_Ant3_dB', ...
    'PLOS_Ant1', 'PLOS_Ant2', 'PLOS_Ant3', ...
    'Best_Antenna_ID'});

outputFile = 'simulacion_compara_3gpp.csv';
writetable(ResultadosExport, outputFile);
fprintf('¡Listo! Archivo "%s" generado con éxito.\n', outputFile);

%% 8. Gráfico de Validación Rápida
figure('Name', 'Mapa de Calor - RSRP Máximo Combinado');
scatter(X(:), Y(:), 10, max_rsrp, 'filled');
colorbar; colormap('turbo'); clim([-115 -65]);
xlabel('Distancia X desde el centro (m)');
ylabel('Distancia Y desde el centro (m)');
title('RSRP Combinado (Best Server) - Malla de 20m');
grid on; axis equal;