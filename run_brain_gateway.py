import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from xiaojuju_core.gateway import serve

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--host",default="127.0.0.1")
    ap.add_argument("--port",type=int,default=12400)
    args=ap.parse_args()
    serve(args.host,args.port)

if __name__=="__main__":
    main()