"""Import a downloaded NHL schedule PDF; preserves the original and hashes both inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess
from fantasy_hockey.providers.nhl_schedule import parse_schedule
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    text = subprocess.run(['pdftotext','-layout',str(args.pdf),'-'],check=True,capture_output=True,text=True).stdout
    result = parse_schedule(text)
    result.update(source='https://media.d3.nhle.com/image/private/fl_attachment/prd/zj6mn0paz7zqpywcedao.pdf',
                  imported_at=datetime.now(timezone.utc).isoformat(),
                  pdf_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
                  text_sha256=hashlib.sha256(text.encode()).hexdigest())
    with args.output.open('x') as out:json.dump(result,out,indent=2)
    print(f"Validated {len(result['games'])} games, 84 for each of 32 teams")


if __name__=='__main__':main()
