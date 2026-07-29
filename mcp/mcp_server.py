import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents" / "hvac-dispatch"))

from company_docs import COMPANY_DOCS

mcp = FastMCP("hvac-business-tools")

# Hardcoded demo service area — zip codes for Georgetown, Round Rock, and Cedar Park, TX.
SERVICE_AREA_ZIP_CODES = {
    "78626",  # Georgetown
    "78628",  # Georgetown
    "78664",  # Round Rock
    "78665",  # Round Rock
    "78613",  # Cedar Park
}

PRICING_ESTIMATES = {
    "tune-up": "$89 to $149",
    "maintenance": "$89 to $149",
    "repair": "$150 to $600, depending on the part and diagnosis",
    "replacement": "$4,500 to $9,500 depending on system size and efficiency rating",
    "installation": "$4,500 to $9,500 depending on system size and efficiency rating",
}


@mcp.tool()
def check_service_area(zip_code: str) -> str:
    """Check whether a given US zip code is inside the company's HVAC service area.

    Use this when a caller or customer asks if we service their location, or
    before booking a job, to confirm the address is within range.

    Args:
        zip_code: A 5-digit US zip code, e.g. "78626".
    """
    if zip_code.strip() in SERVICE_AREA_ZIP_CODES:
        return f"Yes, {zip_code} is within our service area."
    return f"No, {zip_code} is outside our current service area."


@mcp.tool()
def get_business_hours() -> str:
    """Get the company's regular business hours and its emergency service policy.

    Use this when a caller asks whether the business is open, what its hours
    are, or whether emergency/after-hours service is available.
    """
    return " ".join(COMPANY_DOCS[1:3])


@mcp.tool()
def get_pricing_estimate(job_type: str) -> str:
    """Get a rough price range for a given HVAC job type.

    Use this when a caller asks how much a job will cost. Covers common job
    types like "tune-up", "maintenance", "repair", "replacement", and
    "installation". For anything else, this returns a message saying no
    estimate is available rather than guessing a price.

    Args:
        job_type: The kind of job, e.g. "tune-up", "repair", or "replacement".
    """
    estimate = PRICING_ESTIMATES.get(job_type.strip().lower())
    if estimate is None:
        return "no estimate available for that job type"
    return f"Estimated price range for {job_type}: {estimate}."


if __name__ == "__main__":
    mcp.run()
