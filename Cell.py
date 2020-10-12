import bpy
import bmesh
import mathutils

epsilon = 0.000001

class Cell:

    def __init__(self, i , j ): 
        # Variabile che indica se la cella è piena
        self.full = False
        # Indica se la precedente lungo la riga è piena
        self.rowOK = False
        # Indica se la precedente lungo la colonna è piena
        self.columnOk = False
        # Indici celle
        self.i = i
        self.j = j

    # Metodi set
    def setFull(self):
        self.full = True
    def setrowOK(self):
        self.rowOK = True
    def setcolumnOk(self):
        self.columnOk = True

    # Metodo che verifica l'intersezione con il box
    def intersectBox(self, point1, point2, LL, dimX, dimY):
        min_ = mathutils.Vector(( LL.x + ( self.i *  dimX),  LL.y + ( self.j*  dimY)))
        max_ = mathutils.Vector((min_.x +  dimX, min_.y +  dimY))
        if (point1.x > max_.x and point2.x > max_.x) or (point1.x < min_.x and point2.x < min_.x):
            return False
        if (point1.y > max_.y and point2.y > max_.y) or (point1.y < min_.y and point2.y < min_.y):
            return False
        return True
   