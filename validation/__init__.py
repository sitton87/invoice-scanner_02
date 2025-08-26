"""
validation package - מערכת וולידציה מתקדמת ברמת תווים
"""

from .character_kpi_calculator import CharacterKPICalculator
from .validation_processor import ValidationProcessor
from .advanced_validation_gui import AdvancedValidationGUI

__version__ = "1.0.0"
__author__ = "Invoice2Claude"

__all__ = [
    'CharacterKPICalculator',
    'ValidationProcessor', 
    'AdvancedValidationGUI'
]