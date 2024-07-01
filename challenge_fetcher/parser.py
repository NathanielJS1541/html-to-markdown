import requests
import bs4
import challenge_fetcher
import challenge_fetcher.scraper
import challenge_fetcher.challenge
import re


# Basic colour keywords as defined by the CSS3 specification (https://www.w3.org/TR/css-color-3/#valuea-def-color).
BASIC_HTML_COLOURS = [
    "black",
    "silver",
    "gray",
    "white",
    "maroon",
    "red",
    "purple",
    "fuchsia",
    "green",
    "lime",
    "olive",
    "yellow",
    "navy",
    "blue",
    "teal",
    "aqua",
]


"""
CHALLENGE_URL_REGEX is a compiled regular expression that matches strings of the form "problem=<number>":
- "^" asserts the start of a line.
- "problem=" matches the literal string "problem=".
- "(?P<number>\d+)" is a named capturing group to capture one or more digits:
  - "(...)" defines the capture group.
  - "?P<number>" names the capture group "number".
  - "\d" is a shorthand character class to capture digits (0-9).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more digits.
"""
CHALLENGE_URL_REGEX = re.compile(r"^problem=(?P<number>\d+)")

"""
RESOURCE_URL_REGEX is a compiled regular expression that matches strings of the form "resources/<optional_path>/<filename>",
"project/resources/<optional_path>/<filename>", "images/<optional_path>/<filename>", and "project/images/<optional_path>/<filename>":
- "^" asserts the start of a line.
- "(project\/)?" is a capture group that matches the optional literal string "project/".
  - "(...)" defines the capture group.
  - "?" makes the capture group optional.
- "(resources|images)" matches either the literal string "resources" or "images".
  - "(...)" defines the capture group.
  - "resources" matches the literal string "resources".
  - "|" is the OR operator.
  - "images" matches the literal string "images".
- "\/" matches the literal string "/".
- "(.+\/)?" is an optional capture group to match any characters followed by a "/":
  - "(...)" defines the capture group.
  - "." matches any character (except for a newline).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more word characters.
  - "\/" matches the literal "/".
  - "?" makes the capture group optional.
- "(?P<filename>.+)" is a named capturing group to match any characters:
  - "(...)" defines the capture group.
  - "?P<filename>" names the capture group "filename".
  - "." matches any character (except for a newline).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more word characters.
"""
RESOURCE_URL_REGEX = re.compile(
    r"^(project\/)?(resources|images)\/(.+\/)?(?P<filename>.+)"
)

"""
ABOUT_URL_REGEX is a compiled regular expression that matches strings of the form "about=<word>":
- "^" asserts the start of a line.
- "about=" matches the literal string "about=".
- "(\w+)" is a capturing group to capture one or more word characters:
  - "(...)" defines the capture group.
  - "\w" is a shorthand character class to capture word characters (a-z, A-Z, 0-9, _).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more word characters.
"""
ABOUT_URL_REGEX = re.compile(r"^about=(\w+)")

"""
FILE_NAME_REGEX is a compiled regular expression which "sanitises" filenames to remove query strings etc.
- "^" asserts the start of a line.
- "(?:.*_)?" is an optional non-capturing group, which removes the unique ID (i.e. "p096_") from the file name.
  - "(...)" defines the capture group.
  - "?:" denotes that it is a non-capturing group.
  - "." matches any character (except for a newline).
  - "+?" is a lazy quantifier that matches one or more times, but as few times as possible. It allows the previous
    character class to capture one or more characters, but will only allow the group to match up to the first underscore.
  - "_" matches the literal string "_" used to separate the unique ID from the file name.
  - "?" makes the capture group optional.
- "(?P<filename>.*\..+)" is a named capturing group to match the name of the file:
  - "(...)" defines the capture group.
  - "?P<filename>" names the capture group "filename".
  - "." matches any character (except for a newline).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more characters.
  - "\." matches the literal string "." which separates the file name and extension.
  - "." matches any character (except for a newline).
  - "+?" is a lazy quantifier that matches one or more times, but as few times as possible. This is needed to ensure
    the following optional capture group is used if possible.
- "(?:\?.*)?" is an optional non-capturing group, which removes any query strings (i.e. "?1678992052") from the file name.
  - "(...)" defines the capture group.
  - "?:" denotes that it is a non-capturing group.
  - "\?" matches the literal string "?", which separates the file name from the query string.
  - "." matches any character (except for a newline).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more characters.
  - "?" makes the capture group optional.
- "$" asserts the end of a line.
"""
FILE_NAME_REGEX = re.compile(r"^(?:.+?_)?(?P<filename>.+\..+?)(?:\?.*)?$")

"""
LATEX_WORKAROUND_PATTERN is a compiled regular expression which matches inline LaTeX expressions which are immediately
followed by text:
- "(?<!\$)" is a negative lookbehind that asserts what immediately precedes the current position in the string is not a
  dollar sign. This ensures the regex won't match blocks of LaTeX.
- "\$" matches the literal string "$", which is the beginning of a LaTeX expression.
- (?P<expression>[^$]+?) is a named capturing group that captures the contents of the LaTeX expression:
  - "(...)" defines the capture group.
  - "?P<expression>" names the capture group "expression".
  - "[^$]" is a character class that matches any character except the dollar sign:
    - "[...]" defines the character class.
    - "^" is the negation operator, which inverts the following set of characters.
    - "$" is the literal character "$".
  - "+?" is a lazy quantifier that matches one or more times, but as few times as possible. This ensures that only the
    contents of the LaTeX expression are captured.
- "\$" matches the literal string "$", which is the end of a LaTeX expression.
- "(?!\$)" is a negative lookahead that asserts what immediately follows the current position in the string is not a
  dollar sign. This ensures the regex won't match blocks of LaTeX.
- "(?P<text>\w+)" is a named capturing group that captures the text following the LaTeX expression:
  - "(...)" defines the capture group.
  - "?P<text>" names the capture group "text".
  - "\w" is a shorthand character class to capture word characters (a-z, A-Z, 0-9, _).
  - "+" is a greedy quantifier that matches one or more times, and allows the previous character class to capture one or more characters.
"""
LATEX_WORKAROUND_REGEX = re.compile(r"(?<!\$)\$(?P<expression>[^$]+?)\$(?!\$)(?P<text>\w+)?")

"""
MULTILINE_LATEX_REGEX is a compiled regular expression which matches any multi-line LaTeX expression (starting with
\begin{...} and ending with \end{...}) which are not already enclosed in $$..$$.

This is particularly nasty as the re module only supports fixed-length look-behinds. You're welcome...

- "(?<!\$\$)" is a negative look-behind assertion to make sure that the start of the LaTeX expression is not already
  preceded by a "$$":
  - "(?<!...)" is the syntax for a negative lookbehind assertion in regex.
  - "\$\$" matches the literal string "$$".
- "(?<!\$\$\n)" is a negative look-behind assertion to make sure that the start of the LaTeX expression is not already
  preceded by a "$$\n":
  - "(?<!...)" is the syntax for a negative lookbehind assertion in regex.
  - "\$\$" matches the literal string "$$".
  - "\n" matches a newline character.
- "\\begin\{" matches the literal string "\begin{", which is the start of the multi-line LaTeX expression.
- "(\w+?)" is a non-greedy capture group for one or more word characters, to capture the content within the \begin{...}:
  - "\w" is the shorthand character class that matches any word character (equivelant to [a-zA-Z0-9_]).
  - "+?" is a lazy quantifier that matches one or more times, but as few times as possible.
- "\}" matches the literal string "}", which closes the "\begin{...}".
- "((?:.|\n)+?)" is a non-greedy capture group for one or more of any character, or newline:
  - "(...)" is the syntax for a capture group.
  - "(?:.|\n)" is a non-capturing group which matches any character (including newlines):
    - "(?:...)" is the syntax for a non-capturing group.
    - "." matches any character (except for a newline).
    - "|" is the OR operator, which allows matching the pattern before or after it.
    - "\n" matches newlines.
  - "+?" is a lazy quantifier that matches one or more times, but as few times as possible.
- "\\end\{" matches the literal string "\end{", which is the start of the last tag in the multi-line LaTeX expression.
- "(\w+?)" is a non-greedy capture group for one or more word characters, to capture the content within the \end{...}:
  - "\w" is the shorthand character class that matches any word character (equivelant to [a-zA-Z0-9_]).
  - "+?" is a lazy quantifier that matches one or more times, but as few times as possible.
- "\}" matches the literal string "}", which closes the "\end{...}".
- "(?!\$\$)" is a negative lookahead assertion to make sure the end of the LaTeX expression is not already followed by
  a "$$":
  - "(?!...)" is the syntax for a negative lookahead assertion in regex.
  - "\$\$" matches the literal string "$$".
- "(?!\n\$\$)" is a negative lookahead assertion to make sure the end of the LaTeX expression is not already followed
  by a "\n$$":
  - "(?!...)" is the syntax for a negative lookahead assertion in regex.
  - "\n" matches a newline character.
  - "\$\$" matches the literal string "$$".
"""
MULTILINE_LATEX_REGEX = re.compile(r"(?<!\$\$)(?<!\$\$\n)\\begin\{(\w+?)\}((?:.|\n)+?)\\end\{(\w+?)\}(?!\$\$)(?!\n\$\$)")

"""
MULTILINE_LATEX_REPLACEMENT_PATTERN is the replacement pattern for use with the MULTILINE_LATEX_REGEX.

This just wraps the original LaTeX expression inside $$...$$, so that it can render in MarkDown.

- "$$\n" is used to wrap the original LaTeX expression in "$$" on the line above for neatness.
- "\\begin{\1}" replaces the first group of the MULTILINE_LATEX_REGEX, which captured the content within the brackets of
  the "\begin{...}".
- "\2" replaces the contents that was captured in the MULTILINE_LATEX_REGEX between the "\begin{...}" and "\end{...}".
- "\\end{\3}" replaces the last group of the MULTILINE_LATEX_REGEX, which captured the content within the brackets of
  the "\end{...}".
- "\n$$" is used to close the LaTeX expression with a "$$" on the line below for neatness.
"""
MULTILINE_LATEX_REPLACEMENT_PATTERN = r"$$\n\\begin{\1}\2\\end{\3}\n$$"

def parse_contents(
    challenge_number: int,
    response: requests.Response,
    github_workaround: bool,
) -> challenge_fetcher.challenge.Challenge | None:
    """parse_contents Parse the contents of the HTTP response.

    Parses the HTML contained in the HTTP response to create a Challenge object. This contains the relevant information
    to generate a README file such as challenge number, challenge URL, challenge title, challenge description, and
    remote content that needs to be downloaded when the README is created.

    Args:
        challenge_number (int): The number of the Project Euler challenge.
        response (requests.Response): The HTTP response from the HTTP GET request.
        github_workaround (bool): If True, a workaround for the GitHub MarkDown renderer not rendering the LaTeX /opcode function will be applied.

    Returns:
        challenge_fetcher.challenge.Challenge | None: A challenge object representing the parsed challenge data, or None if an error was encountered.
    """

    # If the provided HTTP response has an error code, return None.
    if not response.ok:
        return None

    # Parse the HTML response content into a nice soup we can "pythonically" access.
    # html5lib is used as a parser since some of the HTML on https://projecteuler.net/ does not parse properly using
    # Python's html.parser. See #1 (https://github.com/NathanielJS1541/100_languages_template/issues/1) for more info.
    # html5lib seems to generate HTML slower, but much "truer" to what a browser would display.
    soup = bs4.BeautifulSoup(response.content, "html5lib")

    # On all of the pages from https://projecteuler.net/, the actual problem is contained within a div with the id "content".
    # We are not interested in anything else on the page, so grab that.
    page_content = soup.find("div", id="content")

    # If there is no page content, raise a ValueError as something has gone terribly wrong...
    if page_content is None:
        raise ValueError(f"Page content <div> was not found.")

    # The title is contained within the "content" div, and is contained within h2.
    title = page_content.find("h2").text

    # The description is contained within a div of the "problem_content" class. This is what we need to (somehow)
    # parse into markdown.
    description = page_content.find("div", class_="problem_content")

    # As above, raise a ValueError in the event that the description tag isn't found. This may indicate that the page
    # layout has changed?
    if description is None:
        raise ValueError(f"Problem description <div> was not found.")

    # Convert any URLs embedded in the description to be markdown URLs.
    remote_content = convert_urls_to_markdown(description)

    # Sanitise the description tag content to ensure it can be rendered as MarkDown.
    description_text = sanitise_tag_text(description, github_workaround)

    # Create a new challenge object to return, based on the properties from the page.
    return challenge_fetcher.challenge.Challenge(
        challenge_number,
        response.url,
        title,
        description_text,
        remote_content=remote_content,
    )


def sanitise_file_name(file_name: str) -> str:
    """sanitise_file_name Sanitise the file name of remote content.

    The Project Euler website hosts all resources (such as images and files) in a few central directories, so need
    unique names. When these are downloaded locally, they don't need to have unique names anymore, so this function
    splits off the identifier and keeps the human readable part of the file name. Some file URLs also use a
    query-string, which should be removed from the filename.

    This also strips out any subdirectory names, and takes only the file "stem".

    Args:
        file_name (str): The filename of a remote resource.

    Returns:
        str: The "human readable" part of the filename.
    """

    # Use the compiled regex expression to separate the filename from any additional "fluff".
    filename_match = FILE_NAME_REGEX.search(file_name)

    if not filename_match:
        raise ValueError(
            f"Filename {file_name} could not be parsed using {FILE_NAME_REGEX.pattern}."
        )

    # Return the sanitised filename from the named capture group.
    return filename_match.group("filename")


def convert_tooltips_to_markdown(content: bs4.Tag) -> None:
    """convert_tooltips_to_markdown Replace HTML tooltips with a MarkDown equivelant.

    Args:
        content (bs4.Tag): The bs4 content to replace tooltip tags in.

    Raises:
        NotImplementedError: A tag type that has not been implemented was encountered.
    """

    # Loop through every "span" tag that has the class "tooltiptext".
    for tag in content.find_all("span", class_="tooltiptext"):
        # Get the parent tag, which will reveal the desired formatting of the tooltip.
        parent = tag.parent

        # Get the text that is displayed in the tooltip. This appears in the pop-up.
        tooltip_text = tag.text

        # Remove the tag from the content, as it is no longer needed.
        tag.decompose()

        # Add MarkDown syntax for the formatting style if it is present on the parent tag.
        target_text = get_markdown_from_formatted_tag(parent)

        # If there is no return from get_markdown_from_formatted_tag(parent), then there was no style on the parent
        # tag. In this case, just use the text with no formatting.
        if target_text is None:
            target_text = parent.text

        # Replace the parent tag with the MarkDown representation of a "tooltip".
        # "##" is used so that the link doesn't navigate to the top of the page.
        parent.replace_with(f'[{target_text}](## "{tooltip_text}")')


def get_markdown_from_formatted_tag(tag: bs4.Tag) -> str | None:
    """get_markdown_from_formatted_tag Convert the formatted text in a bs4.Tag to MarkDown syntax.

    Currently supported formatting styles:
    - Italic <i> and <em> tags.
    - Bold <b> and <strong> tags.
    - Span <span> tags used to colour text. (Must have a class matching a colour in BASIC_HTML_COLOURS).

    Note that if the tag does not contain any formatting, None will be returned.

    Args:
        tag (bs4.Tag): The bs4 tag to return the MarkDown equivalent text for.

    Raises:
        NotImplementedError: A tag type was found that has not been implemented.

    Returns:
        str | None: A string representing the formatted tag text. None if no formatting was found.
    """

    # Default to returning None.
    markdown_string = None

    if tag.name == "span":
        # <span> tags are used to colour text. The easiest way (that I know of...) to colour output text in
        # MarkDown is to use LaTeX.

        # IF a span is used to represent a colour, the class stores the colour name.
        # We can assume there is only one class, as the colour name will be checked for validity.
        colour = tag.get("class")[0]

        # Check that the colour is one of the standard HTML colours.
        # Note that if the colour is not a standard colour, the text will not be replaced. The span could represent
        # something else (such as a tooltip) which will be replaced elsewhere.
        if colour in BASIC_HTML_COLOURS:
            # Generate some LaTeX that will set the text within the tag to the specified colour.
            markdown_string = f"\\color{{{colour}}}{{{tag.text}}}"

            # Additionally, MarkDown-style bold and italic syntax aren't compatable with this LaTeX. If there is a <b>,
            # <strong>, <i>, or <em> tag inside the coloured span, we can add a bit of extra LaTeX to reflect this.
            if tag.findChild("b") or tag.findChild("strong"):
                # Use \\bf in front of the LaTeX to make it bold and coloured.
                markdown_string = "\\bf" + markdown_string
            if tag.findChild("i") or tag.findChild("em"):
                # Use \\it in front of the LaTeX to make it italic and coloured.
                markdown_string = "\\it" + markdown_string

            # Finally, replace the tag with the complete LaTeX expression so that it can be rendered inline ($..$).
            markdown_string = f"${{{markdown_string}}}$"
    elif tag.name == "i" or tag.name == "em":
        # <i> and <em> tags should be replaced with MarkDown italic syntax.
        markdown_string = f"*{tag.text}*"
    elif tag.name == "b" or tag.name == "strong":
        # <b> and <strong> tags should be replaced with MarkDown bold syntax.
        markdown_string = f"**{tag.text}**"
    else:
        # If a tag type has not been implemented, throw an error.
        raise NotImplementedError(f'"{tag.name}" tags have not been implemented.')

    return markdown_string


def convert_text_formatting_to_markdown(content: bs4.Tag) -> None:
    """convert_text_formatting_to_markdown Replace formatting tags with MarkDown syntax.

    This uses the get_markdown_from_formatted_tag() method. For supported tags, check the docstring for that function.

    Args:
        content (bs4.Tag): The bs4 content to replace formatting tags in.

    Raises:
        NotImplementedError: A tag type was found that hasn't been implemented.
    """

    # Loop through all formatting tags in the content.
    # Spans must be done first as they MAY need to replace some of the <b> and <i> tags if they are present!
    for tag in content.find_all(["span", "i", "b"]):
        # Get the formatted MarkDown string for the current tag.
        equivalent_string = get_markdown_from_formatted_tag(tag)

        # Only replace the tag if a string was returned. None will be returned if no formatting was found in the tag,
        # in which the tag should be left for the get_string() method to handle later on.
        if equivalent_string is not None:
            tag.replace_with(equivalent_string)


def convert_urls_to_markdown(content: bs4.Tag) -> dict[str, str] | None:
    """convert_urls_to_markdown Convert all URLs in the bs4.Tag to MarkDown links.

    This replaces any <a href=""> tags with the equivelant MarkDown syntax, and additionally corrects those URLs
    based on the type of URL:
      - Links to other challenges are corrected to the full URL to the challenge page on the Project Euler website.
      - Links to remote content are corrected to a link to a file locally, and the file URL is recorded for download.
      - Links to the Project Euler about pages (https://projecteuler.net/about) are updated to full URLs.

    Args:
        content (bs4.Tag): The bs4.Tag containing the challenge descrioption.

    Raises:
        KeyError: Multiple resource files with the same name were found on the page.
        NotImplementedError: An undefined resource type was found on the page.
        NotImplementedError: A tag type was found that has not yet been implemented.

    Returns:
        dict[str, str] | None: A dictionary containing resource URLs keyed by file name to download, or None if no remote content is needed.
    """

    # Create an empty dictionary to store remote content filenames and URLs.
    remote_content = {}

    # Loop through all "a" and "img" tags in the content.
    for tag in content.find_all(["a", "img"]):
        # Initialise to False so that only the img tag detection needs to set it to True.
        is_image = False

        # Get the URL from the tag.
        if tag.name == "a":
            # Resources are stored in anchor tags; the URL is stored in the "href" attribute.
            url = tag.get("href")
        elif tag.name == "img":
            # Images are stored in image tags... (duh...); the URL is stored in the "src" attribute.
            url = tag.get("src")

            # Indicate that the resource to download is an image, as the MarkDown tag needs to be altered.
            is_image = True
        else:
            # If a tag type has not been implemented, throw an error as the attribute to retreive the URL from has not
            # been defined.
            # This should never happen, unless content.find_all(["a", "img"]) is updated...
            raise NotImplementedError(f'"{tag.name}" tags have not been implemented.')

        # Replace the tag with a markdown representation of the link.
        # Also update the remote_content dictionary with any content that needs to be downloaded locally.
        # The is_image indication is needed, since images in MarkDown need a "!"  in front to render them.
        replace_tag_with_markdown_url(tag, url, remote_content, is_image)

    if not remote_content:
        # If no remote content was found, return None.
        return None
    else:
        # If there is remote content, return the dictionary storing it.
        return remote_content


def replace_tag_with_markdown_url(
    tag: bs4.Tag, url: str, remote_content: dict[str, str], is_image: bool
) -> None:
    """replace_tag_with_markdown_url Replace a bs4.Tag with the equivelant MarkDown representation.

    Depending on the URL type, the remote_content dictionary may be updated to include content that needs to be
    downloaded to the specified filename (key) in order for the MarkDown link to work.

    Args:
        tag (bs4.Tag): The tag to replace with MarkDown.
        url (str): The string URL contained within the tag.
        remote_content (dict[str, str]): A dictionary containing the desired filename and URL to the remote content that needs to be downloaded.
        is_image (bool): Indicates that the resource is an image, so the appropriate MarkDown syntax is used.

    Raises:
        KeyError: Multiple resource files with the same name were found on the page.
        NotImplementedError: An undefined resource type was found on the page.
    """

    # Run compiled Regex expressions against the url to determine the type of content.
    # Links to another challenge.
    challenge_match = CHALLENGE_URL_REGEX.search(url)
    # Links to resources such as images and files.
    resource_match = RESOURCE_URL_REGEX.search(url)
    # Links to the Project Euler "about" pages (https://projecteuler.net/about).
    about_match = ABOUT_URL_REGEX.search(url)

    if challenge_match:
        # This type of link is a reference to another challenge.

        # TODO: If problem is going to be downloaded, link it locally.

        # Get the linked challenge number from the named capture group.
        challenge_number = challenge_match.group("number")

        # Construct a URL to the remote challenge page.
        url = f"{challenge_fetcher.scraper.CHALLENGE_URL_BASE}{challenge_number}"

        # For challenge links, preserve the original link text.
        link_text = tag.text
    elif resource_match:
        # This type of link is a reference to a resource such as an image or file. We will download these
        # locally so they can committed to the repo and linked locally in the README.

        # Get the linked file name from the Regex expression's named capture group.
        file_name = sanitise_file_name(resource_match.group("filename"))

        # Construct a URL for the remote content based on the base URL, and the complete URL that the Regex
        # matched.
        remote_url = challenge_fetcher.scraper.URL_BASE + url

        # Swap the "URL" to a local reference to the file_name, so the README will link to the local file once it
        # has been downloaded.
        url = f"./{file_name}"

        # For now, I'm assuming that each page will contain all uniquely named files. This will raise an error
        # if this assumption is incorrect, so I can fix it later :).
        if file_name in remote_content:
            raise KeyError(f"Multiple resources found with the name {file_name}")

        # Add the remote URL to the remote_content dictionary, keyed by the file_name that the resource needs to be
        # downloaded to.
        remote_content[file_name] = remote_url

        # For file and image downloads, ensure the link text or alt text is up to date with the sanitised file name.
        link_text = file_name
    elif about_match:
        # This type of link is a reference to the "about" pages on different topics on the Project Euler website.
        # This content won't be downloaded, and a link to the about page will just be added to the README.

        # The URL from the bs4.Tag will be a relative URL. All we need to do to get a valid URL is add it to the
        # Project Euler base URL.
        url = f"{challenge_fetcher.scraper.URL_BASE}{url}"

        # For "about" links, preserve the original link text.
        link_text = tag.text
    else:
        # Since I don't have the time (or willpower) to download and check every single challenge on the Project
        # Euler website, this error will alert me (or anyone else) to a link type that I haven't come accross yet.
        # If this is raised, inspect the URL and add some more Regex and handling (or open an issue on
        # https://github.com/NathanielJS1541/100_languages_template) :).
        raise NotImplementedError(f"A URL was found to an unknown resource type: {url}")

    # Construct the MarkDown link syntax using the link text and the URL.
    link_text = f"[{link_text}]({url})"

    if is_image:
        # If the link is an image, append an "!" to convert the link syntax to image syntax.
        link_text = "!" + link_text

    # Replace the tag with the MarkDown representation of the new link or image.
    tag.replace_with(link_text)


def latex_regex_repl(match: re.Match[str]) -> str:
    """latex_regex_repl REPL for the GitHub LaTeX workaround re.sub().

    This returns the text that will be used in the substitution based on the capture groups.

    Args:
        match (re.Match[str]): The match from the reegx expression.

    Returns:
        str: The string to replace the matched text.
    """

    # Get the contents of both named capture groups in the LATEX_WORKAROUND_REGEX.
    # Note that the "text" group is optional.
    expression = match.group("expression")
    text = match.group("text")

    # If the optional "text" group was also matched, add it as a text function to the end of the LaTeX expression.
    # Note that all matches of the "expression" group will also call this function. There is no way to avoid returning
    # a replacement string (apart from writing better regex I guess...) so when there is no text group just return the
    # original string.
    if text:
        expression = f"{expression}\\text{{{text}}}"

    # Close the complete expression inside the syntax for a LaTeX inline expression.
    expression = f"${expression}$"

    # Return the expression to use as a replacement.
    return expression


def sanitise_tag_text(description: bs4.Tag, github_workaround: bool) -> str:
def sanitise_tag_text(description: bs4.Tag, github_workarounds: bool) -> str:
    """sanitise_tag_text Sanitise the content of a bs4.Tag, and return it as a string.

    The text content of a bs4.Tag is "sanitised" to ensure that it is compatable with MarkDown. This includes an
    optional workaround for the GitHub MarkDown renderer. The sanitised content is then returned as a string.

    Args:
        description (bs4.Tag): The bs4.Tag containing the challenge description.
        github_workaround (bool): If True, a workaround for the GitHub MarkDown renderer not rendering the LaTeX
        /opcode function will be applied, as well as a workaround for inline LaTeX followed immediately by text not
        rendering correctly on GitHub.

    Returns:
        str: A string that is MarkDown-compatible, which contains the description for the Project Euler challenge.
    """

    # Copy the list of child elements so elements can be removed from description whilst enumerating over them.
    child_elements = description.contents.copy()

    # Loop over each child element to remove them or replace them with formatted text.
    for child in child_elements:
        if child.text.isspace():
            # If the child element is just whitespace, remove it since it will mess up the formatting when the
            # description gets converted to text. In order to mimic the HTML layout in MarkDown, I am relying entirely
            # on tags like <p>, <div> etc. to know where to place newlines.
            description.contents.remove(child)
        else:
            # If there is some text content to the child element, replace it with a text representation of it.
            # strip=False).strip("\n") may seem odd at first, but strip=True would also strip out spaces. I need to
            # ensure that only newlines are removed, so an external call to .strip("\n") is used.
            # The text representation of the child is placed between newlines, so that the text from each element will
            # end up at most two newlines from the next (a paragraph space in MarkDown).
            child_text = "\n" + child.get_text(separator="", strip=False).strip("\n") + "\n"

            # Replace the child with its text representation.
            child.replace_with(child_text)

    # Get the text representation of the description. strip=False is used here to avoid stripping out all of the
    # newlines we just deliberately placed between each element.
    description_text = description.get_text(separator="", strip=False)

    # Strip leading and trailing whitespaces to ensure consistent spacing from the title and footnote when it is added
    # to the MarkDown file.
    description_text = description_text.strip()

    # Some LaTeX expressions do not render correctly as the curly braces \{ and \} do not end up with a backslash. It
    # seems like the backslash is interpreted as an escape character. In order to escape the backslash it must be
    # preceeded with another backslash. To ensure this only alters LaTeX syntax, search for specifically the
    # combination "\{" and "\}", and replace them with "\\{" and "\\}" respectively. Including the escape characters
    # for this ends up looking a bit silly; "\\\\{" and "\\\\}".
    # For more information, see the comment on issue #4:
    # https://github.com/NathanielJS1541/100_languages_template/issues/4#issuecomment-2179358966
    description_text = description_text.replace("\\{", "\\\\{").replace("\\}", "\\\\}")

    # Ensure that multi-line LaTeX expressions (between \begin{...} and \end{...}) are being enclosed in $$..$$ tags.
    # This allows them to correctly render.
    description_text = re.sub(MULTILINE_LATEX_REGEX, MULTILINE_LATEX_REPLACEMENT_PATTERN, description_text)

    # If requested, do the GitHub-specific workarounds.
    if github_workarounds:
        # Workaround for GitHub not supporting \operatorname anymore (see https://github.com/github/markup/issues/1688).
        if "\\operatorname" in description_text:
            # RegEx pattern to replace the occurrances of \operatorname in the description:
            # - "\\operatorname\{" matches the literal string \operatorname{ (with escape character for the \ and {).
            # - "(.+?)" creates a capture group which matches the following:
            #   - "." matches any character.
            #   - "+" quantifier meaning that the previous "." can match one or more times.
            #   - "?" makes the "+" quantifier lazy. It will try and match as few characters as possible while still
            #     matching the next "}".
            # - "\}" matches the literal string }.
            # - "(.+?)" creates another capture group, as above.
            # - "=" matches the literal string = at the end of the expression.
            pattern = r"\\operatorname\{(.+?)\}(.+?)="

            # Replacement expression to define how the capture groups are included in the replaced text:
            # - "\\mathop{\\text{" is the literal string that will replace \operatorname{ with \mathop{\text{.
            # - "\1" is a backreference to the first capture group in the pattern. This corresponds to text captured by
            #   "(.+?)" inside the \\operatorname{...} in the original string.
            # - "}}" is the literal string which will close the \text{} and \mathop{} LaTeX commands.
            # - "\2" is a backreference to the second capture group in the pattern. This corresponds to the text
            #   captured by "(.+?)" between the "}" and "=" in the original string.
            # - "=" is the literal string =, which ends the replacement.
            replacement = r"\\mathop{\\text{\1}}\2="

            # Use the RegEx pattern and replacement strings to replace \operatorname{...} with \mathop{\text{...}} in
            # the description text.
            description_text = re.sub(pattern, replacement, description_text)
        
        # Workaround for GitHub not properly rendering LaTeX immediately followed by text.
        # See #2 (https://github.com/NathanielJS1541/100_languages_template/issues/2).
        # This just adds any text immediately next to an inline LaTeX expression into the LaTeX.
        description_text = re.sub(LATEX_WORKAROUND_REGEX, latex_regex_repl, description_text)

    return description_text
