# MoCapGate native loader v1
import sys
from native_loader import load
sys.modules[__name__] = load("components")
