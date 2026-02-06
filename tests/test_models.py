"""
Tests para modelos de datos (Antenna, Site, Project)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from models.antenna import Antenna, AntennaType, Technology
from models.site import Site
from models.project import Project


class TestAntenna(unittest.TestCase):
    """Test suite para modelo Antenna"""
    
    def test_antenna_creation(self):
        """Verifica creación de antena"""
        antenna = Antenna(
            id="ant001",
            name="Test Antenna",
            latitude=-2.9001,
            longitude=-79.0059,
            height_agl=30.0,
            frequency_mhz=2400,
            tx_power_dbm=43,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800,
            antenna_type=AntennaType.DIRECTIONAL,
            azimuth=45,
            gain_dbi=18
        )
        
        self.assertEqual(antenna.id, "ant001")
        self.assertEqual(antenna.frequency_mhz, 2400)
        self.assertTrue(antenna.enabled)
    
    def test_antenna_serialization(self):
        """Verifica serialización a dict"""
        antenna = Antenna(
            id="ant002",
            name="LTE Sector",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=25,
            frequency_mhz=1800,
            tx_power_dbm=46,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800
        )
        
        data = antenna.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['id'], "ant002")
        self.assertEqual(data['frequency_mhz'], 1800)
        self.assertEqual(data['technology'], 'LTE 1800')
    
    def test_antenna_deserialization(self):
        """Verifica deserialización desde dict"""
        data = {
            'id': 'ant003',
            'name': '5G NR',
            'latitude': -2.9,
            'longitude': -79.0,
            'height_agl': 30,
            'frequency_mhz': 3500,
            'tx_power_dbm': 40,
            'bandwidth_mhz': 100,
            'technology': '5G NR 3500',  # Debe coincidir con el enum
            'antenna_type': 'directional',
            'azimuth': 0,
            'tilt': 3,
            'gain_dbi': 21,
            'horizontal_beamwidth': 65,
            'vertical_beamwidth': 6.5,
            'enabled': True,
            'show_coverage': True
        }
        
        antenna = Antenna.from_dict(data)
        
        self.assertEqual(antenna.id, 'ant003')
        self.assertEqual(antenna.frequency_mhz, 3500)
        self.assertEqual(antenna.technology, Technology.NR_3500)


class TestSite(unittest.TestCase):
    """Test suite para modelo Site"""
    
    def test_site_creation(self):
        """Verifica creación de site"""
        site = Site(
            id="site001",
            name="Test Site",
            latitude=-2.9,
            longitude=-79.0,
            structure_height=35.0
        )
        
        self.assertEqual(site.id, "site001")
        self.assertEqual(site.structure_height, 35.0)
        self.assertEqual(site.address, "")


class TestProject(unittest.TestCase):
    """Test suite para modelo Project"""
    
    def test_project_creation(self):
        """Verifica creación de proyecto"""
        project = Project(
            name="Test Project",
            description="Testing project model"
        )
        
        self.assertEqual(project.name, "Test Project")
        self.assertIsNotNone(project.id)
        self.assertEqual(len(project.antennas), 0)
    
    def test_project_with_antennas(self):
        """Verifica proyecto con antenas"""
        project = Project(name="RF Project")
        
        antenna = Antenna(
            id="ant001",
            name="Test Ant",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=30,
            frequency_mhz=2400,
            tx_power_dbm=43,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800
        )
        
        # antennas es un dict, no una lista
        project.antennas[antenna.id] = antenna
        
        self.assertEqual(len(project.antennas), 1)
        self.assertIn("ant001", project.antennas)
        self.assertEqual(project.antennas["ant001"].id, "ant001")


if __name__ == '__main__':
    unittest.main()
