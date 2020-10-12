import bpy
import bmesh
import mathutils
from . import  Bounding_Box

# Classe Box per QuadTree
class Box():

    # Costruttore con definizioni min e max
    def __init__(self, left, low, right, top):
        self.Min = mathutils.Vector((left,low))
        self.Max = mathutils.Vector((right,top))

    # Metodo che restituisce vero se il rettangolo è contenuto nel box
    def contains(self, rect):
        _min = rect.getLowLeft()
        _max = rect.getTopRight()
        epsilon =  (self.Max.x - self.Min.x)/1000
        if _min.x + epsilon > self.Min.x and _max.x - epsilon  < self.Max.x and _min.y + epsilon > self.Min.y and _max.y - epsilon < self.Max.y:
            return True
        else:
            return False

    # Metodo per verficare l'intersezione
    def intersect(self, left, low, right, top):
        _min = mathutils.Vector((left,low))
        _max = mathutils.Vector((right,top))

        if self.Max.x < _min.x or self.Min.x > _max.x:
            return False
        if self.Max.y < _min.y or self.Min.y > _max.y:
            return False
        return True

    def __str__(self):
        return "Min:" + str(self.Min)  +  ", Max" + str(self.Max)