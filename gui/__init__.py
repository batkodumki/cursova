"""
GUI пакет для методу експертних попарних порівнянь з уточненням переваг
"""

__version__ = "1.0.0"
__author__ = "Курсова робота"

# Імпортуємо тільки моделі (без залежності від tkinter)
from .models import SessionModel, ScaleManager

# Опціонально імпортуємо UI компоненти (потребують tkinter)
try:
    from .app import main
    from .controllers import MainController
    from .views import StartWindow, ProjectSetupWindow, ComparisonWindow, ResultsWindow

    __all__ = [
        'main',
        'MainController',
        'SessionModel',
        'ScaleManager',
        'StartWindow',
        'ProjectSetupWindow',
        'ComparisonWindow',
        'ResultsWindow'
    ]
except ImportError:
    # tkinter недоступний, імпортуємо тільки моделі
    __all__ = [
        'SessionModel',
        'ScaleManager'
    ]
