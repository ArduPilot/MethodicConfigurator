from _typeshed import Incomplete
from collections import deque

class shlex:
    instream: Incomplete
    infile: Incomplete
    posix: Incomplete
    eof: Incomplete
    commenters: str
    wordchars: str
    whitespace: str
    whitespace_split: bool
    quotes: str
    escape: str
    escapedquotes: str
    state: str | None
    pushback: deque
    lineno: int
    debug: int
    token: str
    filestack: deque
    source: Incomplete
    punctuation_chars: Incomplete
    last_wordbreak_pos: Incomplete
    wordbreaks: str
    def __init__(self, instream: Incomplete | None = None, infile: Incomplete | None = None, posix: bool = False, punctuation_chars: bool = False) -> None: ...
    def push_token(self, tok) -> None: ...
    def push_source(self, newstream, newfile: Incomplete | None = None) -> None: ...
    def pop_source(self) -> None: ...
    def get_token(self): ...
    def read_token(self): ...
    def sourcehook(self, newfile): ...
    def error_leader(self, infile: Incomplete | None = None, lineno: Incomplete | None = None): ...
    def __iter__(self): ...
    def __next__(self): ...
    next = __next__
