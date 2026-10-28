"""PCA III: the reviewed BlackRock-only universe, using the PCA II engine."""
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE.parent/'PCA_Four_Axis'))
from build import main

if __name__=='__main__':main(output_base=BASE,reference_only=True)
