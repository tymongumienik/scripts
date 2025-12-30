import sys
import requests
import re

PATTERN: re.Pattern[str] = re.compile(r"^\d{2}\.\d{2}\.[A-Z]$")
BOLD: str = "\033[1m"
RESET: str = "\033[0m"


def verify_code(code: str) -> bool:
    """Check if the PKD code matches the correct format with regex"""
    global PATTERN
    return re.fullmatch(PATTERN, code) is not None


def fetch_info(code: str) -> dict[str, str | list[str]]:
    url: str = f"https://www.pkd.com.pl/wyszukiwarka/pkd/{code}.html"

    try:
        response: requests.Response = requests.get(
            url, headers={"User-Agent": "pkd-label/1.0 (by tymongumienik@github.com)"}
        )
        response.raise_for_status()

        text: str = response.text
        lines: list[str] = text.split("\n")

        lines = [x.strip() for x in lines[lines.index('<section class="py-5">') :]]

        # Name (e.g. Działalność związana z zarządzaniem urządzeniami informatycznymi)
        name: str = (
            next(x for x in lines if x.startswith("<h1 "))
            .split(" - ")[1]
            .removesuffix("</h1>")
        )

        # Description
        description: list[str] = []

        description_lines: list[str] = [
            x for x in lines[lines.index('<div class="wyjasnienie-contener">') :]
        ][2:]
        description_lines = [
            x for x in description_lines[: description_lines.index("</div>")]
        ][:-1]
        description_lines = [
            x
            for x in description_lines
            if x not in ("<ul>", "</ul>", "<section>", "</section>")
        ]

        for line in description_lines:
            if line.startswith("<p>"):
                description.append(line.removeprefix("<p>").removesuffix("</p>"))
            elif line.startswith("<li>"):
                description.append(
                    "- " + line.removeprefix("<li>").removesuffix("</li>")
                )
            else:
                raise ValueError()  # these shouldn't occur (I hope)

        # Related professions (e.g. Programista)
        related_professions_lines: list[str] = [
            x for x in lines[lines.index('<div class="powiazane-id ">') :]
        ]
        related_professions: list[str] = [
            x[x.index("<span>") + 6 : x.index("</span")]
            for x in related_professions_lines
            if "Jakie pkd - <span>" in x
        ]

        # Related codes
        related_codes_lines: list[str] = [
            x
            for x in lines[
                lines.index('<div class="table-responsive">') : lines.index("</table>")
            ]
        ]
        related_codes: list[str] = [
            x[x.index('.html">PKD ') + 11 :].removesuffix("</a></td>")
            for x in related_codes_lines
            if x.startswith('href="/wyszukiwarka/pkd/6') and x.endswith("</td>")
        ]

        return {
            "code": code,
            "name": name,
            "description": description,
            "related_professions": related_professions,
            "related_codes": related_codes,
        }
    except requests.exceptions.Timeout:
        return {"error": "TIMEOUT"}
    except requests.exceptions.HTTPError:
        return {"error": "HTTP"}
    except requests.exceptions.ConnectionError:
        return {"error": "CONNECTION"}
    except Exception:
        return {"error": "UNKNOWN"}


def main(codes: list[str]) -> None:
    for c in codes:
        if not verify_code(c):
            print(f"Error: Code {c} is not a valid PKD code.")
            exit(1)

    for idx, c in enumerate(codes):
        data = fetch_info(c)

        if "error" in data:
            print(
                f"Error while processing code {c}:",
                {
                    "TIMEOUT": "The connection timed out.",
                    "HTTP": "An HTTP error occured.",
                    "CONNECTION": "A connection error occured. Double check if your Internet connection is working!",
                    "UNKNOWN": "An unknown error occured. Report this in the GitHub issues section.",
                }[data],
            )
            exit(1)

        print(f"{data['code']}: {BOLD}{data['name']}{RESET}")
        print(f"{BOLD}Description{RESET}")
        print("\n".join([" " + x for x in data["description"]]))
        print(f"{BOLD}Related professions{RESET}")
        print(", ".join(data["related_professions"]))
        print(f"{BOLD}Related codes{RESET}")
        print(", ".join(data["related_codes"]))

        if idx != len(codes) - 1:
            print("—" * 50)  # em dashes have a use outside AI :)


if __name__ == "__main__":
    args: list[str] = sys.argv
    if len(args) < 2:
        print(
            f"""
Correct usage: uv run {args[0]} <PKD codes seperated by spaces>
Examples:
    uv run {args[0]} 47.91.Z 62.09.Z
    uv run {args[0]} 41.20.Z
        """.strip()
        )
        exit(0)

    main(args[1:])
