"""Parse an uploaded cue file (timing, duration, text) into a list of cues.

Accepted layouts, auto-detected from the first data line:
  CSV   : start,duration,text        (optional header row, quotes allowed)
  Pipe  : 00:04.5 | 5.0 | Hello      (also tab-separated)
Times are seconds ("4.5", "4.5s") or clock style ("1:04.5", "0:01:04.5").
Blank lines and lines starting with '#' are ignored.
"""

import csv
import io
import math

MAX_CUES = 300
MAX_TEXT_CHARS = 1000


class CueError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def parse_time(value):
    s = value.strip().lower()
    if s.endswith("s"):
        s = s[:-1].strip()
    parts = s.split(":")
    if not s or len(parts) > 3:
        raise ValueError(f"cannot read time {value!r}")
    total = 0.0
    for part in parts:
        try:
            number = float(part)
        except ValueError:
            raise ValueError(f"cannot read time {value!r}") from None
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"cannot read time {value!r}")
        total = total * 60 + number
    return total


def _split(line, delimiter):
    if delimiter == ",":
        row = next(csv.reader([line]))
        if len(row) > 3:  # unquoted commas inside the text
            row = row[:2] + [",".join(row[2:])]
        return row
    return line.split(delimiter, 2)


def parse_cues(raw):
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CueError(["File is not valid UTF-8 text."]) from None

    numbered = [
        (number, line.strip())
        for number, line in enumerate(content.splitlines(), start=1)
        if line.strip() and not line.strip().startswith("#")
    ]
    if not numbered:
        raise CueError(["The file has no cue lines."])

    first = numbered[0][1]
    delimiter = "|" if "|" in first else "\t" if "\t" in first else ","

    cues, errors = [], []
    for position, (number, line) in enumerate(numbered):
        row = [cell.strip() for cell in _split(line, delimiter)]
        if len(row) < 3:
            errors.append(f"Line {number}: expected 3 fields (timing, duration, text).")
            continue
        try:
            start = parse_time(row[0])
        except ValueError as error:
            if position == 0:
                continue  # header row
            errors.append(f"Line {number}: {error}.")
            continue
        try:
            duration = parse_time(row[1])
        except ValueError as error:
            errors.append(f"Line {number}: {error}.")
            continue
        text = row[2].strip().strip('"').strip()
        if duration <= 0:
            errors.append(f"Line {number}: duration must be greater than 0.")
        elif not text:
            errors.append(f"Line {number}: text is empty.")
        elif len(text) > MAX_TEXT_CHARS:
            errors.append(f"Line {number}: text is longer than {MAX_TEXT_CHARS} characters.")
        else:
            cues.append({"start": start, "duration": duration, "text": text})

    if not errors and not cues:
        errors.append("The file has no cue lines.")
    if len(cues) > MAX_CUES:
        errors.append(f"Too many cues ({len(cues)}); the limit is {MAX_CUES}.")
    if errors:
        raise CueError(errors)

    for index, cue in enumerate(cues, start=1):
        cue["index"] = index
    return cues
