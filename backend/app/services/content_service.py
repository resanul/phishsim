from __future__ import annotations

import re
from html.parser import HTMLParser

from app.schemas.content import TemplateValidationResult

KNOWN_VARIABLES = {
    "first_name",
    "last_name",
    "department",
    "job_title",
    "company",
    "campaign_name",
    "simulation_link",
}

VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
LINK_PATTERN = re.compile(r'href=["\']([^"\']*)["\']', re.IGNORECASE)


class _HTMLValidator(HTMLParser):
    """Very small structural sanity check: flags obviously unbalanced tags."""

    VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag}> with no matching open tag.")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            self.errors.append(f"Mismatched tag: expected </{self.stack[-1]}> but found </{tag}>.")
            # unwind to keep going
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"Closing tag </{tag}> does not match any open tag.")

    def error(self, message):  # pragma: no cover - py3.9 HTMLParser calls this rarely
        self.errors.append(message)


def extract_variables(text: str) -> set[str]:
    return set(VARIABLE_PATTERN.findall(text or ""))


def validate_template(subject: str, html_body: str, text_body: str = "") -> TemplateValidationResult:
    combined_vars = extract_variables(subject) | extract_variables(html_body) | extract_variables(text_body)
    unknown_vars = sorted(v for v in combined_vars if v not in KNOWN_VARIABLES)

    broken_links: list[str] = []
    for href in LINK_PATTERN.findall(html_body or ""):
        stripped = href.strip()
        if not stripped:
            broken_links.append("(empty href)")
            continue
        if stripped.startswith("{{simulation_link}}"):
            continue
        if stripped.startswith(("http://", "https://", "{{")):
            continue
        if stripped.startswith("#"):
            continue
        broken_links.append(stripped)

    parser = _HTMLValidator()
    html_errors: list[str] = []
    try:
        parser.feed(html_body or "")
        html_errors = list(parser.errors)
        if parser.stack:
            html_errors.append(f"Unclosed tag(s): {', '.join(parser.stack)}")
    except Exception as e:  # pragma: no cover
        html_errors.append(str(e))

    is_valid = not unknown_vars and not broken_links and not html_errors
    return TemplateValidationResult(
        is_valid=is_valid,
        broken_links=broken_links,
        unknown_variables=unknown_vars,
        html_errors=html_errors,
    )


def render_variables(text: str, variables: dict[str, str]) -> str:
    def _sub(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    return VARIABLE_PATTERN.sub(_sub, text or "")
