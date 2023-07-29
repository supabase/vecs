from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple

from .base import AdapterContext, AdapterStep


class MarkdownChunker(AdapterStep):
    """
    MarkdownChunker is an AdapterStep that splits a markdown string into chunks where a heading signifies the start of a chunk, and yields each chunk as a separate record.
    """

    def __init__(self, *, skip_during_query: bool):
        """
        Initializes the MarkdownChunker adapter.

        Args:
            skip_during_query (bool): Whether to skip chunking during querying.
        """
        self.skip_during_query = skip_during_query

    # https://stackoverflow.com/a/13009866
    @staticmethod
    def find_occurrences(s, ch):
        return [i for i, letter in enumerate(s) if letter == ch]

    @staticmethod
    def split_by_heading(md: str, max_tokens: int) -> List[str]:
        lines = md.split("\n")
        chunks = []
        current_chunk = ""

        # a simple for loop would be nice here but I need to be able to get the next item in the list to check for two line headings
        for i, line in enumerate(lines):
            line = lines[i]
            if i != len(lines) - 1:  # if on the last line there is no next line
                next_line = lines[i + 1]
            else:
                next_line = None

            chunk_word_count = len(current_chunk.split(" "))
            line_word_count = len(line.split(" "))

            above_max_tokens = False

            # this is kinda a mess, the aim is to split the line across chunks in the best way possible
            if max_tokens:
                while (
                    line_word_count > max_tokens
                ):  # we must split the line as it is too large to be contained within a single chunk
                    chunks.append(current_chunk)
                    current_chunk = ""

                    full_stop_occurrences = MarkdownChunker.find_occurrences(
                        line, "."
                    )  # preferably we want to split by full stops
                    space_occurrences = MarkdownChunker.find_occurrences(line, " ")

                    closest_full_stop_occurrence = -1

                    # we want to find the full stop at the point closest to the token limit
                    for o in full_stop_occurrences:
                        closest_full_stop_occurrence = (
                            o
                            if o < space_occurrences[max_tokens - 1]
                            else closest_full_stop_occurrence
                        )

                    word_count_at_full_stop = len(
                        MarkdownChunker.find_occurrences(
                            line[0 : closest_full_stop_occurrence + 1], " "
                        )
                    )
                    assert word_count_at_full_stop < max_tokens

                    if closest_full_stop_occurrence != -1:  # if we have a full stop
                        chunks.append(
                            line[0 : closest_full_stop_occurrence + 1]
                        )  # split the string at this full stop and add the first half as a new chunk
                        if (
                            line[closest_full_stop_occurrence + 1] == " "
                        ):  # if the first character after the full stop is a space we remove that as well
                            line = line[
                                closest_full_stop_occurrence + 2 :
                            ]  # remove the first half from the string
                        else:
                            line = line[closest_full_stop_occurrence + 1 :]
                    else:  # otherwise we split by a space
                        chunks.append(line[0 : space_occurrences[max_tokens - 1] + 1])
                        line = line[space_occurrences[max_tokens - 1] + 1 :]

                    chunk_word_count = len(current_chunk.split(" "))
                    line_word_count = len(line.split(" "))

                # back to reasonable code
                above_max_tokens = (
                    chunk_word_count + line_word_count > max_tokens
                    if max_tokens
                    else False
                )

            # print(f"{line} is {'not ' if not MarkdownChunker.is_heading(line, next_line) else ''}heading")
            if MarkdownChunker.is_heading(line, next_line) or above_max_tokens:
                print(current_chunk[-2:])
                chunks.append(current_chunk)
                current_chunk = ""

            current_chunk += f"{line}\n"

        # in case of leftover chunk
        if current_chunk != "":
            chunks.append(current_chunk)

        chunks = [
            chunk[:-1] if chunk.endswith("\n") else chunk for chunk in chunks
        ]  # remove line breaks added to end of chunk

        return filter(
            lambda c: not ((c + " ").isspace()), chunks
        )  # remove empty chunks

    @staticmethod
    def is_heading(line: str, next_line: str) -> bool:
        if (line + " ").isspace():
            return False

        elif line[0] == "#":  # normal markdown headings
            # we iterate over the string
            # if we meet a character that is not a '#' without a space preceding it, this is not a valid heading
            # if we have more than 6 '#' this is also not valid

            last_char = (
                ""  # initialise to empty string so we don't have a bad comparison
            )
            for index, char in enumerate(line):

                if char != "#":
                    if (
                        char == " " and last_char == "#"
                    ):  # end of hashes, start of text, valid heading
                        return True
                    elif (
                        char != " "
                    ):  # no space between hashes and other characters, invalid heading
                        return False
                elif index == 6:  # more than 6 hashes, invalid heading
                    return False
                last_char = char

        elif next_line in [
            "",
            None,
        ]:  # if the next line is blank or None then it can't be a two line heading (see below)
            return False

        elif next_line[0] in [
            "-",
            "=",
        ]:  # markdown also supports headings level 1 and 2 by having a line of equals or dashes underneath respectively
            return all(
                char == next_line[0] for char in next_line
            )  # true if every character in the line is the same (a '-' or a '=')

    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,
        max_tokens: int = None,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        """
        Splits each markdown string in the records into chunks where each heading starts a new chunk, and yields each chunk
        as a separate record. If the `skip_during_query` attribute is set to True,
        this step is skipped during querying.

        Args:
            records (Iterable[Tuple[str, Any, Optional[Dict]]]): Iterable of tuples each containing an id, a markdown string and an optional dict.
            adapter_context (AdapterContext): Context of the adapter.
            max_tokens (int): The maximum number of tokens per chunk

        Yields:
            Tuple[str, Any, Dict]: The id appended with chunk index, the chunk, and the metadata.
        """
        if max_tokens and max_tokens < 1:
            raise ValueError("max_tokens must be a nonzero positive integer")

        if adapter_context == AdapterContext("query") and self.skip_during_query:
            for id, markdown, metadata in records:
                yield (id, markdown, metadata or {})
        else:
            for id, markdown, metadata in records:
                headings = MarkdownChunker.split_by_heading(markdown, max_tokens)
                for heading_ix, heading in enumerate(headings):
                    yield (
                        f"{id}_head_{str(heading_ix).zfill(3)}",
                        heading,
                        metadata or {},
                    )
