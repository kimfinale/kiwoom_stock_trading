try:
    import pykiwoom
    print("pykiwoom is installed")
    from pykiwoom.kiwoom import Kiwoom
    print("Kiwoom imported from pykiwoom")
except ImportError:
    print("pykiwoom is NOT installed")
except Exception as e:
    print(f"Error: {e}")
