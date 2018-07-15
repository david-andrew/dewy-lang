class Number:

    #class for representing numbers in the dewy langauge


    def __init__(self, value, mode=0, category=None):
        self.value = value
        self.mode = mode
        self.category = category

        #modes:
        #0 - raw -> string representation of the number
        