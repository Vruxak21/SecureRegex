"""
Lexer package — public API.

Usage
-----
    from app.lexer import tokenize, Token, TokenType

    tokens = tokenize("(a|b)*abb")
"""

from app.lexer.token import Token, TokenType
from app.lexer.lexer import tokenize

__all__ = ["Token", "TokenType", "tokenize"]
