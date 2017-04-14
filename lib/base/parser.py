#!/usr/bin/env python

from paranoia.base import paranoia_agent
from paranoia.base import declaration

__all__ = ['ParserState', 'Parser', 'ParserError']

class ParserError(paranoia_agent.ParanoiaError):
    pass

class ParserState(object):
    def __init__(self, unconsumed, read, want):
        self.unconsumed = unconsumed
        self.read = read
        self.want = want

class Parser(object):
    STATE_CONSUME = 0
    STATE_FEED = 1
    STATE_DONE = 2
    
    def __init__(self, decl):
        if not isinstance(decl, declaration.Declaration):
            raise ParserError('decl must be a Declaration object')
        
        self.declaration = decl
        self.gen_obj = self.generate()
        self.tape = self.gen_obj.next()
        self.state = Parser.STATE_CONSUME

    def consume(self):
        if not self.state == Parser.STATE_CONSUME:
            raise ParserError('parser not ready for consumption')

        parse_state = self.gen_obj.next()
        consumed = self.tape[:parse_state.read]
        self.tape = parse_state.unconsumed

        if parse_state.want == 0:
            self.state = Parser.STATE_DONE
            self.gen_obj.close()
        else:
            self.state = Parser.STATE_FEED

        self.last_state = parse_state
        return consumed

    def feed(self, data=None):
        if not self.state == Parser.STATE_FEED:
            raise ParserError('parser not ready for feeding')

        if data is None:
            data = self.tape

        if not len(data):
            raise ParserError('unexpected end of file')
            
        self.gen_obj.send(data)
        self.state = Parser.STATE_CONSUME

    def run(self):
        while not self.state == Parser.STATE_DONE:
            if self.state == Parser.STATE_CONSUME:
                self.consume()
            elif self.state == Parser.STATE_FEED:
                self.feed()

    def generate(self):
        yield []
        yield ParserState([], 0, 0)
