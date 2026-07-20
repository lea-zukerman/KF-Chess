def parse_script(text):
    return [line.strip() for line in text.splitlines() if line.strip()]
