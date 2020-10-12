import bpy
import bmesh
import mathutils
from . import  Bounding_Box
from . import Box

MAX_LEVEL = 5

# Classe nodo del QuadTree
class QuadTreeNode():

    # Costruttore del nodo con coordinate box, bounding box contenuti, lista di nodi e livello
    def __init__(self, left, low, right, top, lvl):
        self.box = Box.Box(left, low, right, top)
        self.Bbox_list = []
        self.Nodes = []
        self.level = lvl
        for i in range(0,4):
            self.Nodes.append(None)

    # Suddivide il box in 4 quadranti creando 4 nodi figli
    def subdivide(self):
        left = self.box.Min.x
        low = self.box.Min.y
        right = self.box.Max.x 
        top = self.box.Max.y 
        dist = (self.box.Max.y - self.box.Min.y)/2

        self.Nodes[0] = QuadTreeNode(left, low + dist, left + dist, top, self.level + 1)
        self.Nodes[1] = QuadTreeNode(left + dist, low + dist, right, top, self.level + 1)
        self.Nodes[2] = QuadTreeNode(left, low, left + dist , low + dist, self.level + 1)
        self.Nodes[3] = QuadTreeNode(left + dist, low, right, low + dist, self.level + 1)

    # Metodo per inserimento di un bounding box
    def insert(self, rect):
        # Se non è stata definita la lista di nodi figli e il livello è minore del livello massimo
        if self.Nodes[0] == None and self.level < MAX_LEVEL:
            # Suddivide il nodo corrente
            self.subdivide()

        stored = False
        i = 0
        # Per ogni nodo si verifica se il bounding box è contenuto nel nodo
        if self.Nodes[0] != None:
            while i < 4 and not stored:
                node = self.Nodes[i]
                if node.box.contains(rect):
                    node.insert(rect)
                    stored = True
                i = i + 1
        if not stored:
            self.Bbox_list.append(rect.index)

   # Metodo per restiruire la lista bounding box nei nodi intersecati 
    def collide(self, left, low, right, top):
        toScan = []
        if self.Nodes[0] != None:
            for node in self.Nodes:   
                if node.box.intersect(left, low, right, top):    
                    toScan += node.collide(left, low, right, top)

        return toScan + self.Bbox_list

    # Metodo per restituire il nodo sottoforma di stringa
    def __str__(self):
        toString = ""
        for i in range(0, self.level):
            toString = toString + " - "

        toString  = toString + self.box.__str__() +  ":"
        for bbox in self.Bbox_list:
            toString = toString + str(bbox) + "  "
        toString += '\n' 

        if self.Nodes[0] != None:
            for node in self.Nodes:
                toString = toString + node.__str__()
        
        return toString
