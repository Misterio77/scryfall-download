#!/usr/bin/env nix-shell
#! nix-shell -i python
#! nix-shell -p upscayl-ncnn "python3.withPackages(p: [p.requests])"

from urllib3.util import Url
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from typing import Optional
import fileinput
import re
import requests


def download_file(url: Url, target: Path):
    r = requests.get(url)
    r.raise_for_status()
    open(target, "wb").write(r.content)


@dataclass
class CardEntry:
    qty: Optional[int]
    name: Optional[str]
    setcode: Optional[str]
    collector_number: Optional[str]
    PATTERN = re.compile(
        r'^"?(?:(\d+)(?:x)? )?([^()]+?)(?: \((\w+)\)(?: ([^" ]+))?)?"?$'
    )

    @classmethod
    def parse(cls, text: str) -> Optional["CardEntry"]:
        m = cls.PATTERN.match(text.strip())
        if m and any(m.groups()):
            (qty, name, setcode, cn) = m.groups()
            return CardEntry(int(qty) if qty else None, name, setcode, cn)
        else:
            return None

    def to_card(self) -> Optional["Card"]:
        # Try first with exact CN and set
        if self.collector_number and self.setcode:
            r = requests.get(
                f"https://api.scryfall.com/cards/{self.setcode}/{self.collector_number}"
            )
            if not r:
                return None
            data = r.json()
        # If not, search by name and optionally set
        elif self.name:
            r = requests.get(
                "https://api.scryfall.com/cards/named",
                params={"exact": self.name, "set": self.setcode},
            )
            data = r.json()
            if not r:
                return None
        # Else, we couldn't find it
        else:
            return None
        # Double sided
        if "card_faces" in data:
            front = data["card_faces"][0]
            name_front = front["name"]
            image_uri_front = front["image_uris"]["png"]
            back = data["card_faces"][1]
            name_back = back["name"]
            image_uri_back = back["image_uris"]["png"]
        # Single sided
        else:
            name_front = data["name"]
            image_uri_front = data["image_uris"]["png"]
            name_back = None
            image_uri_back = None
        return Card(
            name_front=name_front,
            image_uri_front=image_uri_front,
            name_back=name_back,
            image_uri_back=image_uri_back,
            setcode=data["set"],
            collector_number=data["collector_number"],
        )


@dataclass
class Card:
    name_front: str
    image_uri_front: str
    name_back: Optional[str]
    image_uri_back: Optional[str]
    setcode: str
    collector_number: str

    def download_faces(self, output_dir: str):
        directory = Path(output_dir)
        download_file(
            Url(self.image_uri_front),
            directory
            / (self.name_front + self.setcode + self.collector_number + "front" + ".png"),
        )
        if self.image_uri_back and self.name_back:
            download_file(
                Url(self.image_uri_back),
                directory
                / (self.name_back + self.setcode + self.collector_number + "back" + ".png"),
            )


def parse_input() -> list[CardEntry]:
    entries: list[CardEntry] = []
    print("Parsing input", end="", flush=True)
    for line in fileinput.input():
        line = line.strip()
        if entry := CardEntry.parse(line):
            print(".", end="", flush=True)
            entries.append(entry)
        elif line == "":
            # Skip empty line
            continue
        else:
            raise Exception(f"Invalid line '{line}'")
    print("done")
    return entries


def fetch_cards(entries: list[CardEntry]) -> list[Card]:
    cards: list[Card] = []
    print("Fetching card data", end="", flush=True)
    for entry in entries:
        if card := entry.to_card():
            print(".", end="", flush=True)
            cards.append(card)
        else:
            raise Exception(f"Failed to find card {entry.name}")
    print("done")
    return cards


def download_cards(cards: list[Card], directory: str):
    print("Downloading cards", end="", flush=True)
    for card in cards:
        card.download_faces(directory)
        print(".", end="", flush=True)
    print("done")


def upscayl(input_path: str, output_path: str, model: str):
    print("Upscaling cards", end="", flush=True)
    cmd = ["upscayl-bin", "-i", input_path, "-o", output_path, "-n", model]
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, bufsize=1, encoding="utf-8")
    if p.stderr:
        for line in iter(p.stderr.readline, ""):
            if "Upscayled Successfully!" in line:
                print(".", end="", flush=True)
    print("done")
    print("Cards saved to", output_path)


def main():
    entries = parse_input()
    cards = fetch_cards(entries)
    with TemporaryDirectory(delete=True, dir="/tmp") as tmp:
        download_cards(cards, tmp)
        with TemporaryDirectory(
            prefix="upscaled_cards", delete=False, dir="/tmp"
        ) as upscaled_dir:
            upscayl(tmp, upscaled_dir, "realesrgan-x4plus-anime")


if __name__ == "__main__":
    main()
