#!/usr/bin/env nix-shell
#! nix-shell -i python
#! nix-shell -p upscayl-ncnn "python3.withPackages(p: [p.requests])"

import io
import subprocess
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from typing import Optional
import fileinput
import re
import requests


@dataclass
class CardEntry:
    qty: Optional[int]
    name: Optional[str]
    setcode: Optional[str]
    collector_number: Optional[str]
    PATTERN = re.compile(
        r'^"?(?:(\d+)(?:x)? )?([^()]+?)(?: \((\w+)\))?(?: (?:#)?(\d+))?"?$'
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
        if self.collector_number and self.setcode:
            return Card.new(self.setcode, self.collector_number)
        elif self.name:
            return Card.new_named(self.name, self.setcode)
        else:
            return None


@dataclass
class Card:
    name: str
    setcode: str
    collector_number: str
    image_uri: str

    @classmethod
    def new(cls, setcode: str, collector_number: str) -> Optional["Card"]:
        r = requests.get(f"https://api.scryfall.com/cards/{setcode}/{collector_number}")
        r.raise_for_status()
        data = r.json()
        return Card(
            data["name"],
            data["set"],
            data["collector_number"],
            data["image_uris"]["png"],
        )

    @classmethod
    def new_named(cls, name: str, setcode: Optional[str]) -> Optional["Card"]:
        r = requests.get(
            "https://api.scryfall.com/cards/named",
            params={
                "exact": name,
                "set": setcode,
            },
        )
        if r:
            data = r.json()
            return Card(
                data["name"],
                data["set"],
                data["collector_number"],
                data["image_uris"]["png"],
            )
        else:
            return None


def download_cards(cards: list[Card], directory: str):
    print("Downloading cards", end="", flush=True)
    for card in cards:
        filename = directory + "/" + card.name + ".png"
        r = requests.get(card.image_uri)
        r.raise_for_status()
        open(filename, "wb").write(r.content)
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


def main():
    cards: list[Card] = []
    print("Parsing input...")
    for line in fileinput.input():
        if entry := CardEntry.parse(line):
            if card := entry.to_card():
                cards.append(card)
    print("Found:", cards)
    with TemporaryDirectory(delete=True, dir="/tmp") as tmp:
        download_cards(cards, tmp)
        with TemporaryDirectory(delete=False, dir="/tmp") as upscaled_dir:
            upscayl(tmp, upscaled_dir, "realesrgan-x4plus-anime")
            print("Cards saved to", upscaled_dir)


if __name__ == "__main__":
    main()
