import urllib.parse
import json
import requests
from bs4 import BeautifulSoup
from InquirerPy import inquirer
import webbrowser
import tempfile

BASE_URL: str = "https://justjoin.it"


def fetch_data_payload(
    url: str = BASE_URL, required_phrase: str = "Choose language"
) -> str:
    """Fetch the data payload from supplied URL"""
    try:
        response: requests.Response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("The connection timed out.")
    except requests.exceptions.HTTPError:
        raise RuntimeError("An HTTP error occured.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "A connection error occured. Double check if your Internet connection is working!"
        )

    soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
    script = next(s for s in soup.find_all("script") if required_phrase in s.text)
    raw: str = script.text.removeprefix("self.__next_f.push(").removesuffix(")")
    _, payload = json.loads(raw)
    return payload


def extract_form(data: dict, key: str) -> list[dict[str, str]]:
    """Extract form input data by key"""
    return [
        {"slug": x["slug"], "label": x["label"], "value": x["value"]}
        for x in data["formInputsData"][key]
    ]


def unique_labels(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Remove duplicates based on label"""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for x in items:
        if x["label"] not in seen:
            seen.add(x["label"])
            out.append(x)
    return out


def select_single_choice(
    message: str, choices: list[str], allow_all: bool = False
) -> str:
    """Single selection via InquirerPy"""
    if allow_all:
        choices = ["All locations"] + choices
    return inquirer.fuzzy(message=message, choices=choices).execute()


def select_multiple_choice(message: str, choices: list[str]) -> list[str]:
    """Multiple selection via InquirerPy"""
    return inquirer.checkbox(
        message=message,
        choices=choices,
        validate=lambda x: len(x) > 0,
        invalid_message="At least one selection must be made",
        vi_mode=True,
    ).execute()


def main() -> None:
    print("Fetching data...")
    payload: str = fetch_data_payload()
    data: dict = json.loads(payload[payload.find(":") + 1 :])[3]["children"][3]
    print("\033[A" * 2)  # clear previous line

    # city
    cities = unique_labels(extract_form(data, "cities"))
    city = select_single_choice(
        "Select city:", [c["label"] for c in cities], allow_all=True
    )
    city_slug: str = next(c["slug"] for c in cities if c["label"] == city)

    # radius
    radius_slug: str | None = None
    if city_slug != "all-locations":
        radiuses_data = extract_form(data, "distanceOptions")
        radius = select_single_choice(
            f"Select maximum distance from {city}:", [x["label"] for x in radiuses_data]
        )
        radius_slug = next((x["slug"] for x in radiuses_data if x["label"] == radius))

    # workplace
    workplaces_data = extract_form(data, "remoteWorkOptions")
    workplace_selection = select_multiple_choice(
        "Select workplace type (space for selection, enter for confirmation):",
        [x["label"] for x in workplaces_data],
    )
    workplace_slug: str = ",".join(
        x["slug"] for x in workplaces_data if x["label"] in workplace_selection
    )

    # salary
    salary_slug: str | None = None
    if inquirer.confirm(
        message="Do you want to set a minimum salary?", default=True, vi_mode=True
    ).execute():
        salary_slug: str = inquirer.text(
            message="Enter minimum salary (e.g. 6500):",
            validate=lambda x: len(x) > 0 and x.isdigit(),
            invalid_message="Salary must be an integer",
        ).execute()

    # experience level
    experience_levels_data = extract_form(data, "experienceLevels")
    experience_selection = select_multiple_choice(
        "Select experience level (space for selection, enter for confirmation):",
        [x["label"] for x in experience_levels_data],
    )
    experience_slug: str = ",".join(
        x["slug"] for x in experience_levels_data if x["label"] in experience_selection
    )

    # employment type
    employment_data = extract_form(data, "employmentTypes")
    employment_selection = select_multiple_choice(
        "Select employment type (space for selection, enter for confirmation):",
        [x["label"] for x in employment_data],
    )
    employment_slug: str = ",".join(
        x["slug"] for x in employment_data if x["label"] in employment_selection
    )

    # working times
    working_times_data = extract_form(data, "workingTimes")
    working_times_selection = select_multiple_choice(
        "Select working times (space for selection, enter for confirmation):",
        [x["label"] for x in working_times_data],
    )
    working_times_slug: str = ",".join(
        x["slug"] for x in working_times_data if x["label"] in working_times_selection
    )

    # search query
    search_query: str = inquirer.text(
        message="Enter search query (leave empty to skip):", vi_mode=True
    ).execute()

    url: str = f"{BASE_URL}/job-offers/{city_slug}?"
    params: dict[str, str] = {
        "orderBy": "DESC",
        "working-hours": working_times_slug,
        "workplace": workplace_slug,
        "experience-level": experience_slug,
        "employment-type": employment_slug,
    }
    if radius_slug:
        params["radius"] = radius_slug
    if salary_slug:
        params["salary"] = f"{salary_slug},500000"
        params["with-salary"] = "yes"
    if search_query:
        params["keyword"] = search_query

    query_string: str = urllib.parse.urlencode(params)
    url: str = f"{BASE_URL}/job-offers/{city_slug}?{query_string}"

    print("Fetching offers...")
    print("\033[A" * 2)  # clear previous line

    try:
        offers_payload = fetch_data_payload(url, "isSuperOffer").removesuffix('\n"')
        offers_payload = offers_payload[offers_payload.find(":[") + 1 :].strip()
        offers_data = json.loads(offers_payload)[3]["state"]["queries"]
        offers: list[dict] = next(
            (x for x in offers_data if "niceToHaveSkills" in str(x))
        )["state"]["data"]["pages"][0]["data"]

        data: list[dict] = []

        for offer in offers:
            salary = None
            for e in offer["employmentTypes"]:
                # always prefer permanent over B2B (obviously)
                if not (salary is None and e["type"] == "b2b"):
                    continue

                salary = {
                    "type": e["type"],
                    "gross": e["gross"],
                    "timespan": e["unit"],
                    "range": {
                        "from": e["fromPln"],
                        "to": e["toPln"],
                    },
                }

            data.append(
                {
                    "url": f"{BASE_URL}/job-offer/{offer['slug']}",
                    "title": offer["title"],
                    "company": {
                        "name": offer["companyName"],
                        "logo": offer["companyLogoThumbUrl"],
                    },
                    "date": {
                        "published": offer["publishedAt"],
                        "expires": offer["expiredAt"],
                    },
                    "metadata": {
                        "salary": salary,
                        "skills": offer["requiredSkills"],
                        "workplace": offer["workplaceType"],
                        "hours": offer["workingTime"],
                    },
                    "cities": [e["city"] for e in offer["multilocation"]],
                }
            )

        with open("page.htmltemplate") as template:
            template_content: str = template.read()

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp.write(
                template_content.replace(
                    "<script>", f"<script>window.jobOffers = {json.dumps(data)};"
                ).encode("utf-8")
            )
            tmp.flush()

            webbrowser.open(tmp.name)

    except StopIteration:
        print("No job offers with that criteria found :(")
        exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        print(f"Error: {e}")
