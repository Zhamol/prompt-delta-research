def parse_line(line):
    parts = line.split(" ")
    return {"timestamp": parts[0], "level": parts[1], "message": parts[2]}

def parse_lines(lines):
    return [parse_line(line) for line in lines]
