from datetime import datetime


class StreamingTimestamper:
    """
    A class that provides streaming relative timestamps for output lines.
    Instead of processing all lines at the end, this timestamps each line
    as it's received with a relative time from when the object was created.
    """

    def __init__(self):
        self.start_time = datetime.now()

    def timestamp_line(self, line: str) -> str:
        """
        Add a relative timestamp to a line of text.
        The timestamp shows seconds elapsed since the StreamingTimestamper was created.
        """
        now = datetime.now()
        delta = now - self.start_time
        seconds = delta.total_seconds()
        return f"{seconds:3.2f} {line.rstrip()}"
