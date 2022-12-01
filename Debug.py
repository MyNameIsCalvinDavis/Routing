import time
import sys
import random
import os
random.seed(123)


# ms precision, if possible
start = int(time.time() * 1000)

class bcolors:
    BLACK =     "\033[30m"
    RED =       "\033[31m"
    GREEN =     "\033[32m"
    YELLOW =    "\033[33m"
    BLUE =      "\033[34m"
    MAGENTA =   "\033[35m"
    CYAN =      "\033[36m"
    WHITE =     "\033[37m"
    UNDERLINE = "\033[21m"
    RESET =     "\033[0m"

class Debug:
    
    ID_color_map = {}
    extended_not_white = [x for x in range(0, 256) if x not in \
        [15, 251, 252, 253, 254, 255, 188, 7, 159, 123, 122, 158, 230, 231, 224, 225]
        ]

    def __init__(self, ID, *args, color="white", f=None):
        if f: f = os.path.basename(f)
        else: f = ""
        
        text = ""
        for item in args:   
            if type(item) == type({}): # Printing a dict
                text += Debug.color(item, Debug.getColor("white")) + " "
            elif type(item) == type([]):
                for i in item:
                    text += Debug.color(i, Debug.getColor("white")) + " "
            elif item in Debug.ID_color_map: # Printing an ID
                text += Debug.colorID(item) + Debug.getColor(color) + " "
            else:
                text += Debug.getColor(color) + str(item) + " "
        text = text[:-1] # Remove the last space

        # Map the incoming host to a random extended color
        if not ID in Debug.ID_color_map:
            Debug.ID_color_map[ID] = "\u001b[38;5;{0}m".format(random.choice(Debug.extended_not_white), bcolors.RESET)
        
        self.s = "{:<15} {:<30}|{} {}".format(
            Debug.color( str(self._getms() - start).zfill(6), "blue" ),
            Debug.color( f, "yellow" ),
            Debug.colorID( ID ),
            Debug.color( text, color )
        )
        print(self.s, flush=True)
    
    def __str__(self):
        return self.s

    def _getms(self):
        return int(time.time() * 1000)
    
    @staticmethod
    def color(text, color):
        # Choose a name, or provide an ANSI color code
        if color.isalpha():
            color = Debug.getColor(color)

        return bcolors.RESET + color + str(text) + bcolors.RESET
    
    @staticmethod
    def getColor(color):
        if color.lower() == "black": return bcolors.BLACK
        if color.lower() == "red": return bcolors.RED
        if color.lower() == "green": return bcolors.GREEN
        if color.lower() == "yellow": return bcolors.YELLOW
        if color.lower() == "blue": return bcolors.BLUE
        if color.lower() == "magenta": return bcolors.MAGENTA
        if color.lower() == "cyan": return bcolors.CYAN
        if color.lower() == "white": return bcolors.WHITE
        if color.lower() in ["ul", "underline"]: return bcolors.UNDERLINE

        #raise ValueError(color + " not a debug color")
    
    def colorID(ID):
        # Colors the given ID based on the class variable ID_color_map
        if not ID in Debug.ID_color_map:
            Debug.ID_color_map[ID] = "\u001b[38;5;{0}m".format(random.choice(Debug.extended_not_white), bcolors.RESET)
        
        color = Debug.ID_color_map[ID]
        #if Debug.user_color:
        #    return bcolors.RESET + color + ID + bcolors.RESET + Debug.getColor(Debug.user_color)
        #else:
        return bcolors.RESET + color + ID + bcolors.RESET

if __name__ == "__main__":

    l = [x for x in range(10)] + [21] + [x for x in range(30, 48)] + [53] + [x for x in range(90, 109)]
    print("Basic:")
    for i in l:
        print("{1}\033[{0}m{0}{1}".format(i, bcolors.RESET), end=" ")
    print("\nBold:")
    for i in l:
        print("{1}\033[{0};1m{0}{1}".format(i, bcolors.RESET), end=" ")
    print("\nExtended:")
    for i in range(0, 256):
        print("{1}\u001b[38;5;{0}m{0}{1}".format(i, bcolors.RESET), end=" ")
    print()

    Debug("A", "Hello", "blue")
    time.sleep(1)
    Debug("B", "goodbye")
