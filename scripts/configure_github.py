"""Configure non-secret OIDC repository variables using the local Git credential helper.

Never prints or stores credentials. Run only as the repository administrator.
"""

import subprocess

import requests

REPO = "ankyo-gh/azure-forum"
VARIABLES = {
    "AZURE_CLIENT_ID": "4434c9b9-15d3-474a-ab94-0dddaecc622a",
    "AZURE_TENANT_ID": "8d41d6d7-36ce-4e0c-8c6d-cf2c54c39039",
    "AZURE_SUBSCRIPTION_ID": "2351e4b2-3a33-40db-b6f8-1c4de902bad6",
}


def github_session():
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
    )
    credentials = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": "Bearer " + credentials["password"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def main():
    session = github_session()
    endpoint = f"https://api.github.com/repos/{REPO}/actions/variables"
    for name, value in VARIABLES.items():
        response = session.get(f"{endpoint}/{name}", timeout=30)
        if response.status_code == 404:
            response = session.post(endpoint, json={"name": name, "value": value}, timeout=30)
        elif response.ok:
            response = session.patch(
                f"{endpoint}/{name}", json={"name": name, "value": value}, timeout=30
            )
        if not response.ok:
            raise SystemExit(f"Repository variable {name}: HTTP {response.status_code}")
        print(f"Configured {name}")


if __name__ == "__main__":
    main()
