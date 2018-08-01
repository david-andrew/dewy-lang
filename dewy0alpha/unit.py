#from collections import namedtuple

class Unit:
    """Class for representing any physical units. Mainly for SI, but optionally other units as well"""
    
        # for now, skipping hecto, deca, deci, (maybe micro->should be actual mu symbol in unicode)
    # include empty for optional no prefix. make sure empty is last so that non-emptys match first
    SI_short_prefixes = {'E':18, 'P':15, 'T':12, 'G':9, 'M':6, 'k':3, 'c':-2, 'm':-3, 'mu':-6, 'n':-9, 'p':-12, 'f':-15, 'a':-18}
    
    SI_long_prefixes = {'exa':18, 'peta':15, 'tera':12, 'giga':9, 'mega':6, 'kilo':3, 'centi':-2, 'milli':-3, 'micro':-6, 'nano':-9, 'pico':-12, 'femto':-15, 'atto':-18}
    
    SI_short_units = {'m':0, 'g':1, 's':2, 'A':3, 'K':4, 'mol':5, 'cd':6}
    
    SI_long_units = {'meter':0, 'metre':0, 'gram':1, 'second':2, 'amp':3, 'ampere':3, 'kelvin':4, 'mole':5, 'candela':6}
    
    SI_short_derived_units = {'Hz':7, 'rad':8, 'sr':9, 'N':10, 'Pa':11, 'J':12, 'W':13, 'C':14, 'V':15, 'F':16, 'omega':17, 'ohm':17, 'S':18, 'Wb':19, 'T':20, 'H':21, 'deg C':22, 'lm':23, 'lx':24, 'Bq':25, 'Gy':26, 'Sv':27, 'kat':28}
    
    SI_long_derived_units = {'hertz':7, 'radian':8, 'steradian':9, 'newton':10, 'pascal':11, 'joule':12, 'watt':13, 'coulomb':14, 'volt':15, 'farad':16, 'ohm':17, 'siemens':18, 'weber':19, 'tesla':20, 'henry':21, 'degree celsius':22, 'degrees celsius':22, 'lumen':23, 'lux':24, 'becquerel':25, 'gray':26, 'sievert':27, 'katal':28}
    
    other_short_units = []#['deg', 'B', 'bit']
    
    other_long_units = []#['degree', 'byte', 'bit']#, 'minute' 'second', 'hour', 'day', 'year', 'century', 'centuries']
    
    other_short_prefixes = []#['Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi']
    
    other_long_prefixes = []#['kibi','mebi', 'gibi', 'tebi', 'pebi', 'exbi', 'zebi', 'yobi'] #for bytes/bits only?



    SI_prefix_strings = {18:'E', 15:'P', 12:'T', 9:'G', 6:'M', 3:'k', -2:'c', -3:'m', -6:'mu', -9:'n', -12:'p', -15:'f', -18:'a'}
    SI_unit_strings = {-1:'unitless', 0:'m', 1:'g', 2:'s', 3:'A', 4:'K', 5:'mol', 6:'cd', 7:'Hz', 8:'rad', 9:'sr', 10:'N', 11:'Pa', 12:'J', 13:'W', 14:'C', 15:'V', 16:'F', 17:'Ω', 18:'S', 19:'Wb', 20:'T', 21:'H', 22:'deg C', 23:'lm', 24:'lx', 25:'Bq', 26:'Gy', 27:'Sv', 28:'kat'}


    def __init__(self, prefix=None, unit=None, mode=-1): #default mode is raw
        
        if mode == -1: #parse the raw unit into a value

            mode = 0 #start with mode 0, unless derived unit is recognized

            if prefix is None:
                prefix = 0
            elif prefix in Unit.SI_short_prefixes:
                prefix = Unit.SI_short_prefixes[prefix]
            elif prefix in Unit.SI_long_prefixes:
                prefix = Unit.SI_long_prefixes[prefix]
            else:
                raise ValueError('Unit Error: unrecognized prefix value "' + prefix + '"')

            if unit is None:
                unit = -1 #unitless
                mode = 0
            elif unit in Unit.SI_short_units:
                unit = Unit.SI_short_units[unit]
            elif unit in Unit.SI_long_units:
                unit = Unit.SI_long_units[unit]
            elif unit in Unit.SI_short_derived_units:
                unit = Unit.SI_short_derived_units[unit]
                mode = 1
            elif unit in Unit.SI_long_derived_units:
                unit = Unit.SI_long_derived_units[unit]
                mode = 1
            else:
                raise ValueError('Unit Error: unrecognized unit type "' + str(unit) + '"')
        

        #currently just for raw representation
        self.prefix = prefix #prefix should probably be a list for the units that are in mode 2 and 3
        self.unit = unit
        

        #how is the unit being represented
        self.mode = mode

        #modes: - what about dimensional units e.g. [length] [time] [mass] etc.
        #-1 - raw -> string of the literal unit name
        #0 - single basic -> int from 0 to 6 to represent the unit. {-1:none 0:meter, 1:gram, 2:second, 3:amp, 4:kelvin, 5:mol, 6:candela}
        #1 - single complex -> int from 0 to 28 to represent all SI base and derived units
        #2 - multi basic -> 7-dimensional vector holding the exponent of each of the 7 base units
        #3 - multi complex -> n-dimensional vector holding the exponent of every available unit
        #others?

    
    #these should return physical units in cases of non-matching prefixes    
    def __add__(self, other):
        if type(other) != Unit:
            return NotImplemented

        if self == other:
            mode = max(self.mode, other.mode)
            if mode == 0 or mode == 1:
                #easiest addition
                return PhysicalNumber(1, other.prefix - self.prefix, Unit.clone(self.as_mode(mode))) #assuming both SI units

            elif mode == 2 or mode == 3:
                scale = 1 #currently assuming all scales are equal. need to fix for mode 3 (e.g. rad/s to Hz)
                exponent = sum(tuple(other_prefix*other_pow-self_prefix*self_pow for self_prefix, self_pow, other_prefix, other_pow in zip(self.as_mode(mode).prefix, self.as_mode(mode).unit, other.as_mode(mode).prefix, other.as_mode(mode).unit)))
                unit = Unit.clone(self).as_mode(mode)
                return PhysicalNumber(scale, exponent, unit) 
        else:
            raise ValueError('Unit Error: Attmpted to add non-matching units  ' + str(self) + ' to ' + str(other))
             
    def __mul__(self, other):
        if type(other) != Unit:
            return NotImplemented

        mode = max(self.mode, other.mode)
        
        if mode == 0 or mode == 1:
            length = 7 if mode == 0 else 28
            mode = 2 if mode == 0 else 3 #mode of combined unit
            
            if self == other:
                scale = other.prefix - self.prefix
                unit = tuple(2 if i == self.unit else 0 for i in range(length))
                prefix = tuple(self.prefix if i == self.unit else 0 for i in range(length))
                return PhysicalNumber(value=1, exponent=scale, unit=Unit(prefix, unit, mode))
            
            else:
                unit = tuple(1 if (i == self.unit or i == other.unit) else 0 for i in range(length))
                prefix = tuple(0 if (i != self.unit and i != other.unit) else (self.prefix if i == self.unit else other.prefix) for i in range(length))
                return PhysicalNumber(value=1, exponent=0, unit=Unit(prefix, unit, mode))
        
        elif mode == 2 or mode == 3:
            length = 7 if mode == 2 else 28
            self = self.as_mode(mode)
            other = other.as_mode(mode)

            scale = sum((other_prefix - self_prefix) * (other_unit) if (self_unit * other_unit != 0) else 0 for self_prefix, other_prefix, self_unit, other_unit in zip(self.prefix, other.prefix, self.unit, other.unit))
            

            prefix = tuple(self_prefix if self_unit != 0 else other_prefix for self_prefix, self_unit, other_prefix in zip(self.prefix, self.unit, other.prefix)) #use prefixes from self over prefixes from other (unless self doesn't have that unit)
            unit = tuple(self_unit + other_unit for self_unit,other_unit in zip(self.unit, other.unit))
            return PhysicalNumber(value=1, exponent=scale, unit=Unit(prefix, unit, mode))

    def __sub__(self, other):
        if type(other) != Unit:
            return NotImplemented

        return self + other

    def __mod__(self, other):
        if type(other) != Unit:
            return NotImplemented

        return self / other
    
    def __truediv__(self, other):
        if type(other) != Unit:
            return NotImplemented

        prod = self * other #useful for how other scales relative to self

        mode = max(self.mode, other.mode)

        if self == other:
            return PhysicalNumber(1, -prod.exponent, Unit(None, None))
        else:
            if mode == 0 or mode == 1:
                length = 7 if mode == 0 else 28
                mode = 2 if mode == 0 else 3 #mode of combined unit

                unit = tuple(0 if (i != self.unit and i != other.unit) else (1 if i == self.unit else -1) for i in range(length))
                prefix = tuple(0 if (i != self.unit and i != other.unit) else (self.prefix if i == self.unit else other.prefix) for i in range(length))
                return PhysicalNumber(value=1, exponent=0, unit=Unit(prefix, unit, mode))
        
            elif mode == 2 or mode == 3:
                length = 7 if mode == 2 else 28
                self = self.as_mode(mode)
                other = other.as_mode(mode)

                scale = -prod.exponent #sum((other_prefix - self_prefix) * other_unit for self_prefix, other_prefix, other_unit in zip(self.prefix, other.prefix, other.unit))
                prefix = tuple(self_prefix if self_unit != 0 else other_prefix for self_prefix, self_unit, other_prefix in zip(self.prefix, self.unit, other.prefix)) #use prefixes from self over prefixes from other (unless self doesn't have that unit)
                unit = tuple(self_unit - other_unit for self_unit,other_unit in zip(self.unit, other.unit))
                return PhysicalNumber(value=1, exponent=scale, unit=Unit(prefix, unit, mode))

    # probably implement it so that it pairs with mod (%)
    # def __floordiv__(self, other): #return the scale between the two units
    #     mode == max(self.mode, other.mode)
    #     if mode == 0 or mode == 1:
    #         return self.prefix - other.prefix
    #     if mode == 2 or mode == 3:
    #         return sum([i - j for i, j in zip(self.prefix.as_mode(mode), other.prefix.as_mode(mode))])

    def __pow__(self, power):
        if not isinstance(power, (int, float, complex)):
            return NotImplemented

        if power != 0:
            if self.mode == 0 or self.mode == 1:
                length = 7 if self.mode == 0 else 28
                prefix = tuple(self.prefix if i == self.unit else 0 for i in range(length))
                unit = tuple(power if i == self.unit else 0 for i in range(length))
                mode = 2 if self.mode == 0 else 3
                unit = Unit(prefix, unit, mode)
                return PhysicalNumber(value=1, exponent=0, unit=unit)
            elif self.mode == 2 or self.mode == 3:
                length = 7 if self.mode == 2 else 28
                prefix = tuple(self.prefix)
                unit = tuple(u * power for u in self.unit)
                mode = self.mode
                unit = Unit(prefix, unit, mode)
                return PhysicalNumber(value=1, exponent=0, unit=unit)
        else:
            return PhysicalNumber(1, 0, Unit(None, None))


        # if self.mode == 0  or self.mode == 2:
        #     mode = 2
        #     s = self.as_mode(mode)
        # elif self.mode == 1 or self.mode == 3:
        #     mode = 3
        #     s = self.as_mode(3)
        # return Unit(s.prefix, tuple([i*power for i in s.unit]), mode)


    def __eq__(self, other): #checks to make sure that the units are compatible, not that the units are the same
        if self.mode == other.mode:
            return self.unit == other.unit # and self.prefix == other.prefix
        else:
            mode = max(self.mode, other.mode)
            return self.as_mode(mode) == other.as_mode(mode)

    def __ne__(self, other):
        return not self == other


    def __str__(self):
        
        if self.mode == 0 or self.mode == 1:
            if self.prefix in Unit.SI_prefix_strings:
                prefix = Unit.SI_prefix_strings[self.prefix]
                unit = Unit.SI_unit_strings[self.unit]
                return '{}{}'.format(prefix,unit)
            elif self.prefix == 0:
                return Unit.SI_unit_strings[self.unit]
            else:
                raise ValueError('unknown prefix for unit found *10^' + str(self.prefix))
                
        
        elif self.mode == 2 or self.mode == 3:
            ret = ''
            for prefix, unit, i in zip(self.prefix, self.unit, range(len(self.prefix))):
                if unit != 0:
                    if unit == 1:
                        ret = ret + ' ' + ('' if prefix == 0 else Unit.SI_prefix_strings[prefix]) + Unit.SI_unit_strings[i]
                    else:
                        ret = ret + ' ' + ('' if prefix == 0 else Unit.SI_prefix_strings[prefix]) + Unit.SI_unit_strings[i] + '^' + str(unit)

            return ret[1:] #skip first space
        
        
    def __repr__(self):
        return 'Unit(prefix={}, unit={}, mode={})'.format(self.prefix, str(self.unit), self.mode)
       
    
    def simplify(self, mode=-1):
        """simplify the unit to the specified mode level, or if no mode is given, simplify as much as possible"""

        #make unit conversions as neccessary
        print('simplifying ' + str(self) + ' is not currently implemented')

        pass

    def is_unitless(self):
        #check if the unit it unitless
        if self.mode == 0 or self.mode == 1:
            return True if self.unit == -1 else False
        elif self.mode == 2 or self.mode == 3:
            unitless = True
            for u in self.unit:
                unitless = unitless and u == 0
            return unitless



    @staticmethod
    def create_unit(prefix, unit): #convert a raw unit to a unit in mode 1 or 2
        mode = 0 #start with mode 0, unless derived unit is recognized

        if prefix is None:
            prefix = 0
        elif prefix in Unit.SI_short_prefixes:
            prefix = Unit.SI_short_prefixes[prefix]
        elif prefix in Unit.SI_long_prefixes:
            prefix = Unit.SI_long_prefixes[prefix]
        else:
            raise ValueError('Unit Error: unrecognized prefix value "' + prefix + '"')

        if unit in Unit.SI_short_units:
            unit = Unit.SI_short_units[unit]
        elif unit in Unit.SI_long_units:
            unit = Unit.SI_long_units[unit]
        elif unit in Unit.SI_short_derived_units:
            unit = Unit.SI_short_derived_units[unit]
            mode = 1
        elif unit in SI_long_derived_units:
            unit = SI_long_derived_units[unit]
            mode = 1
        else:
            raise ValueError('Unit Error: unrecognized unit type "' + unit + '"')

        return Unit(prefix, unit, mode)

    @staticmethod
    def clone(clone):
        assert type(clone) == Unit
        return Unit(clone.prefix, clone.unit, clone.mode)

    def as_mode(self, mode): #convert a unit from it's current mode to the mode specified
        if self.mode == mode:
            return Unit(self.prefix, self.unit, self.mode)
        else:


            if self.mode == 0:
                if mode == 1: #do noething because this is already correctly represented (simply change the mode number)
                    return Unit(self.prefix, self.unit, mode)
                elif mode == 2 or mode == 3:
                    size = 7 if mode == 2 else 28
                    return Unit(tuple(0 if i != self.unit else self.prefix for i in list(range(size))), tuple(0 if i != self.unit else 1 for i in list(range(size))), mode)
                
            elif self.mode == 1:
                if mode == 0:
                    if self.unit > 7:
                        raise ValueError('Unit Error: Unable to convert ' + str(self) + ' to mode 0 because it is not a simple base unit')
                    else:
                        return Unit(self.prefix, self.unit, mode) #do nothing because the value should already be correct
                elif mode == 2:
                    raise ValueError('currently unimplemented. need to have unit conversion to base units available')
                elif mode == 3:
                    size = 28
                    return Unit(tuple(0 if i != self.unit else self.prefix for i in list(range(size))), tuple(0 if i != self.unit else 1 for i in list(range(size))), mode)

            elif self.mode == 2:
                if mode == 0 or mode == 1:
                    s = sum([abs(i) for i in self.unit]) 
                    if s == 1:
                        index = self.unit.index(1)
                        prefix = self.prefix[index]
                    elif s == 0:
                        index = -1
                        prefix = 0
                    else:
                        raise ValueError('Unit Error: cannot convert complex unit ' + str(self) + ' to mode ' + str(mode) + ' single simple unit')

                    return Unit(prefix, index, mode)

                elif mode == 3:
                    size = 28
                    return Unit(tuple(self.prefix[i] if i < len(self.unit) else 0 for i in list(range(size))), tuple(self.unit[i] if i < len(self.unit) else 0 for i in list(range(size))), mode)

            elif self.mode == 3:
                if mode == 0 or mode == 1:
                    s = sum([abs(i) for i in self.unit])
                    if s == 1:
                        index = self.unit.index(1)
                        prefix = self.prefix[index]
                    elif s == 0:
                        index = -1
                        prefix = 0
                    else:
                        raise ValueError('Unit Error: cannot convert complex unit ' + str(self) + ' to mode ' + mode + ' single simple unit')

                    if mode == 0 and index > 6:
                        raise ValueError('Unit Error: cannot convert unit ' + str(self) + ' to mode 0 because it is a derived unit')
                    return Unit(prefix, index, mode)

                elif mode == 2:
                    if sum([abs(i) for i in self.unit[7:]]) > 0:
                        raise ValueError('Currently unimplemented conversion from complex units into simpler form')
                    else:
                        size = 7
                        return Unit(tuple(self.prefix[i] for i in list(range(size))), tuple(self.unit[i] for i in list(range(size))), mode)
    

        
    @staticmethod
    def match_units(text):
        #match the current text with an SI unit and optional prefix
        #no multiplications, spaces, or divisions -> those will be handled on subsequent scanner passes
        
        #rules
        #SI units are incorrect if they are followed by an alphanumeric character
        #SI unit = ([short prefix] , short base unit) | ([long prefix] , long base unit)
        #short prefix = E | P | T | G | M | k | h | c | m | mu | n | p | f | a
        #short base unit = m | g | s | A | K | mol | cd
        #long prefix = exa | peta | tera | giga | mega | kilo | centi | milli | micro | nano | pico | femto | atto
        #long base unit = (meter,[s]) | (gram,[s]) | (second,[s]) | (amp,[s]) | kelvin | (mole,[s]) | (candela,[s])
        #
        # note that the gram is not an actual base unit, it is just the base word. the kilogram is the base unit
        
        #hertz Hz, radians rad, newtons N, pascals Pa, joules J, watts W, coulombs C, volts V, farad F, ohm Omega, siemens S, weber Wb, tesla T, henry H, degrees Celsius deg C (no prefixes?), lumen lm, lux lx, becquerel Bq, gray Gy, sievert Sv, katal kat

            
        if len(text) < 20:
            text += ' ' * 25 # add extra text to the end, if the length is not long enough
                
                
        #match short SI prefixes (G, M, k, c, m, n, etc.)
        for p in {**Unit.SI_short_prefixes, **{'':0}}:    #include empty to allow for no prefix
            if text.startswith(p):
                        
                #match short SI units (m, g, s, etc.)
                for u in Unit.SI_short_units:
                    if text.startswith(u, len(p)):
                        if not text[len(p)+len(u)].isalnum():
                            return (p, u)
                                
                #match short derived SI units (Pa, N, rad, Hz, etc.)
                for u in Unit.SI_short_derived_units:
                    if text.startswith(u, len(p)):
                        if not text[len(p)+len(u)].isalnum():
                            return (p, u)
                                        
        #for written out units, capitalization doesn't matter, and can be singular or plural
        #match long SI prefixes (giga, mega, kilo, centi, etc.)
        for p in {**Unit.SI_long_prefixes, **{'':0}}:    #include empty to allow for no prefix
            if text.lower().startswith(p):
                                                
                #match long SI units (meter, gram, second, etc.) with optional 's' on the end
                for u in Unit.SI_long_units:
                    if text.lower().startswith(u, len(p)):
                        if text[len(p) + len(u)] in 'sS':    #if 's' is at the end of the unit. what if plural ends in 'es'?
                            u += 's'
                            raise ValueError('currently plural units will cause a bug to occur')
                        if not text[len(p) + len(u)].isalnum():
                            return (p, u)
                                                            
                for u in Unit.SI_long_derived_units:
                    if text.lower().startswith(u, len(p)):
                        if text[len(p) + len(u)] in 'sS':
                            u += 's'
                            raise ValueError('currently plural units will cause a bug to occur')
                        if not text[len(p) + len(u)].isalnum():
                            return (p, u)
                        
        #look for other units? liters, etc.
        
        #if no units are found
        return None



class PhysicalNumber:
    """Class for representing a number with a unit"""

    #TODO - CHANGE "exponent" TO ORDER OF MAGNITUDE "order"?
    def __init__(self, value, exponent=None, unit=None): #none means unspecified, not no unit
        self.value = value
        self.exponent = exponent
        self.unit = Unit.clone(unit) if unit is not None else unit

    def __add__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        unit = self.unit + other.unit #physical number with scale between self and other
        return PhysicalNumber(self.value + unit.value * 10**unit.exponent * other.value, self.exponent, Unit.clone(unit.unit))

    def __radd__(self, other):
        return self+other

    def __sub__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None))

        unit = self.unit - other.unit #physical number with scale between self and other
        return PhysicalNumber(self.value - unit.value * 10**unit.exponent * other.value, self.exponent, Unit.clone(unit.unit))

    def __rsub__(self, other):
        
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        return other - self

    def __mul__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        unit = self.unit * other.unit #physical number for scale between a and b
        return PhysicalNumber(self.value * other.value, unit.exponent + self.exponent + other.exponent, unit.unit)
        
    def __rmul__(self, other):
        return self * other

    def __mod__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        #self and other are both physical numbers
        if self.unit.is_unitless() and other.unit.is_unitless():
            return (self.value * 10**self.exponent) % (other.value * 10**other.exponent)
        else:
            raise NotImplementedError('Attempted to mod (%) numbers with units: ' + str(self) + ' % ' + str(other) + '.\nThis will probably be implemented in the future.')
        #raise NotImplementedError('% is not yet implemented for physical numbers')
        # unit = self.unit % other.unit
        # if type(unit) == PhysicalNumber:
        #     num = self.value % (other.value * unit.value)
        #     unit = unit.unit
        # else:
        #     num = self.value % other.value

        # return PhysicalNumber(num, unit)

    def __rmod__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        return other % self

    def __truediv__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        scale = self.unit / other.unit
        value = self.value / other.value

        return PhysicalNumber(value * scale.value, scale.exponent, scale.unit)


    def __rtruediv__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        return other / self

    def __pow__(self, power):
        if not isinstance(power, (int, float, complex, PhysicalNumber)):
            return NotImplemented
        if isinstance(power, (int, float, complex)):
            return self ** PhysicalNumber(1,power,Unit())

        if power.unit.is_unitless(): #unitless
            power = power.value * 10 ** power.exponent
            if power == 0:
                return PhysicalNumber(value=1, exponent=0, unit=Unit())
            else:
                num = self.value ** power
                exponent = self.exponent * power
                unit = (self.unit ** power).unit
                return PhysicalNumber(value=num, exponent=exponent, unit=unit)
        else:
            raise ValueError('Cannot perform operation ' + str(self) + '^ (' + str(power) + '). Exponent must be unitless, but has unit ' + str(power.unit))

    def __rpow__(self, other):
        if type(other) == Unit:
            other = PhysicalNumber(1, 0, other)
        elif isinstance(other, (int, float, complex)):  
            other = PhysicalNumber(other, 0, Unit(None,None)) 

        return other**self

    def __neg__(self):
        return PhysicalNumber(-self.value, self.exponent, self.unit)

    def __pos__(self):
        return self

    def __abs__(self):
        return PhysicalNumber(abs(self.value, self.exponent, self.unit))

    # def __invert__(self):
    #     raise NotImplementedError('')

    def __lshift__(self, other):
        if self.is_integer() and other.is_integer():
            return PhysicalNumber(self.value << other.value, exponent=0, unit=Unit())
        else:
            raise ValueError('Tried to << non-unitless numbers: ' + str(self) + ' << ' + str(other))

    def __rshift__(self, other):
        if self.is_integer() and other.is_integer():
            return PhysicalNumber(self.value >> other.value, exponent=0, unit=Unit())
        else:
            raise ValueError('Tried to >> non-unitless numbers: ' + str(self) + ' >> ' + str(other))
    
    def __and__(self, other):
        if self.is_integer() and other.is_integer():
            return PhysicalNumber(self.value & other.value, 0, Unit())
        else:
            raise ValueError('Tried to AND non-unitless numbers: ' + str(self) + ' and ' + str(other))

    def __or__(self, other):
        if self.is_integer() and other.is_integer():
            return PhysicalNumber(self.value | other.value, 0, Unit())
        else:
            raise ValueError('Tried to OR non-unitless numbers: ' + str(self) + ' or ' + str(other))

    def __xor__(self, other):
        if self.is_integer() and other.is_integer():
            return PhysicalNumber(self.value ^ other.value, 0, Unit())
        else:
            raise ValueError('Tried to XOR non-unitless numbers: ' + str(self) + ' xor ' + str(other))

    def __invert__(self):
        if self.is_integer():
            return PhysicalNumber(~self.value, 0, Unit())

    def __eq__(self, other):
        raise NotImplementedError('== is not yet implemented for physical numbers')
        # if self.unit == other.unit:
        #     (self / other)
                    
        # scale = self.unit // other.unit
        pass

    def __ne__(self, other):
        raise NotImplementedError('!= is not yet implemented for physical numbers')

    def __str__(self):
        s = ''
        space = False
        if self.value != 1:
            s += str(self.value)
            space = True
        if self.exponent != 0:
            s += ' ' if space else ''    
            s += '10^' + str(self.exponent)
            space = True
        if self.unit.is_unitless():
            if not space:
                #i.e. only writing the unit, and it is unitless
                s = '1'
        else:
            s += ' '
            s += str(self.unit)
        
        return s

    def __repr__(self):
        return 'PhysicalNumber(value={}, exponent={} unit={})'.format(self.value, self.exponent, repr(self.unit))

    def is_integer(self):
        return isinstance(self.value, int) and self.exponent == 0 and self.unit.is_unitless()

#class Unit -> defined in unit.py