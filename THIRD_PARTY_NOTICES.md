# Third-party notices

The original mostly-unique-code fixture in `examples/mostly_unique_code.original.txt` contains CPython's `json.decoder` source obtained with `inspect.getsource` from Python 3.13.18 in the pinned tokenizer image. The corresponding dictionary, template, grammar, and delta files encode that same source. Delta history variants include a whitespace change and an appended comment, as described in the research report; the original source fixture is otherwise unchanged.

Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved.

The runtime's complete license notice is retained in [third_party/CPython-LICENSE.txt](third_party/CPython-LICENSE.txt). The upstream project is [python/cpython](https://github.com/python/cpython).

The project uses the separately distributed [tiktoken](https://github.com/openai/tiktoken/tree/0.12.0) library and downloads its public tokenizer vocabularies when reproducing counts. The library, Docker image layers, and vocabulary cache are not vendored into this repository. Recorded vocabulary hashes are included.

No blanket open-source license for the new research code has been selected. These notices preserve the terms of included third-party material and do not relicense it.
