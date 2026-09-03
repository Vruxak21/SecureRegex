"""
Parser package — public API.

Usage
-----
    from app.parser import parse, parse_pattern

    ast = parse_pattern("(a|b)*abb")
    print(ast.to_dict())
"""

from app.parser.parser import parse, parse_pattern

__all__ = ["parse", "parse_pattern"]
