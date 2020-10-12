import bpy
import bmesh
import mathutils
import math
import time
import multiprocessing as mp

from . import Cell

epsilon = 0.0001

# Metodo per il calocolo del segno delle coordinate geometriche
def computeBarCoord( v1, v2, px, py):

    return (v2.x - v1.x)*(py - v1.y) - (v2.y - v1.y)*(px - v1.x)

# Classe bounding box
class Bounding_Box():
    # Numero celle per lato della bitmap
    numCelle_x = 30
    numCelle_y = 30

    # Costruttore
    def __init__(self, faces, uv_layer, idx, mrg, min_, max_):
        # Facce che compongono la mesh
        self.mesh = faces
        # Variabile che indica se attivo il packing interno
        self.inside = False
        # Indice del box
        self.index = idx 
        # Livello uv
        self.uv_layer = uv_layer
        # Matrice per bitmap
        self.matrix = []
        # Lista posizioni per packing interno
        self.positions = []
        # Numero celle piene
        self.fullCells = 0
        # Variabile che indica se bitmap totalmente piena
        self.complete = False
        # Variabile che indica se non è possibile inserire elemento adiacente
        self.totFull = False
         # Variabile che indica se superiormente è occupata
        self.topComplete = False
        # DImensione cella bitmap
        self.dimY = 0
        self.dimX = 0        
        # coordinata y dell'elemento adiacente più in alto
        self.lastY = -1
        # Coordinate Udim
        self.udim_X = 0
        self.udim_Y = 0
        # Coordinate del box          
        self.Low_Left  = mathutils.Vector((min_.x , min_.y))
        self.Low_Right = mathutils.Vector((max_.x, min_.y))
        self.Top_Left  = mathutils.Vector((min_.x , max_.y))
        self.Top_Right = mathutils.Vector((max_.x, max_.y))
        # Posizione iniziale
        self.PosIn = self.Low_Left
        

    # Algoritmo per la creazione delle bitmap
    def rasterize(self):
        self.inside = True
        # Dimensioni celle
        self.dimX = self.base()/self.numCelle_x
        Cell.Cell.dimX = self.dimX
        self.dimY = self.height()/self.numCelle_y
        Cell.Cell.dimY = self.dimY
        # Variabile per calcolo tempo computazionale
        a = 0

        # Definizione la matrice di dimensione numCelle_x * numCelle_y
        ta = time.time()
        for i in range(0, self.numCelle_x):
            appList =[] 
            for j in range(0, self.numCelle_y):
                c = Cell.Cell( i, j)
                appList.append(c)
            self.matrix.append(appList)
        b = time.time()
        a = a + b- ta

        # Per ogni faccia nella mesh
        for face in self.mesh:
            # Calcolo bounding box del triangolo
            minx = 10
            miny = 10
            maxx = -1
            maxy = -1
            vertices = []
            for loop in face.loops:
                loop_uv = loop[self.uv_layer]
                coord_x = loop_uv.uv.x
                coord_y = loop_uv.uv.y
                vertices.append(loop_uv.uv.xy - self.Low_Left)
                if coord_x > maxx:
                    maxx = coord_x
                if coord_x < minx:
                    minx = coord_x
                if coord_y > maxy:
                    maxy = coord_y
                if coord_y < miny:
                    miny = coord_y       
            imx =  int((minx - self.Low_Left.x)/self.dimX)
            imy =  int((miny - self.Low_Left.y)/self.dimY)
            iMx =  int((maxx - self.Low_Left.x)/self.dimX)
            iMy =  int((maxy - self.Low_Left.y)/self.dimY)

            if iMx!=self.numCelle_x:
                iMx = iMx + 1
            if iMy!=self.numCelle_y:
                iMy = iMy + 1
            
            # Per ogni pixel nel bounding box
            for i in range (imx, iMx):
                prec = False 
                for j in range(imy, iMy):
                    # Se non è pieno
                    if not self.matrix[i][j].full:
                        # Si calcola il segno dell coordinate baricentriche
                        s_alpha = computeBarCoord(vertices[0], vertices[1], i * self.dimX ,  j * self.dimY )
                        s_beta  = computeBarCoord(vertices[1], vertices[2], i * self.dimX ,  j * self.dimY )
                        s_gamma = computeBarCoord(vertices[2], vertices[0], i * self.dimX ,  j * self.dimY )                     
                        # Se tutte positive
                        if s_alpha >= -0.01 and s_beta >= -0.01 and s_gamma >= -0.01:
                            # Si riempie la cella
                            self.matrix[i][j].setFull()
                            self.fullCells = self.fullCells + 1

        # se tutte le celle sono occupate, si considera la matrice totalemente piena
        if self.fullCells == self.numCelle_x * self.numCelle_y:
            self.complete = True
        else:
            # Altrimenti si cercano le possibili posizioni per il packing
            self.findPositions()
            
        return a
        


    # Ricerca della posizione dopo la creazione delle matrici
    def findPositions(self):

        #scansione per righe
        for i in range(0, self.numCelle_x):
            prec = True
            for j in range(0, self.numCelle_y):
                if prec and not self.matrix[i][j].full:
                    self.matrix[i][j].setrowOK()
                    prec = False
                else:
                    if self.matrix[i][j].full:
                        prec = True
                    else:
                        prec= False
        
        #scansione per colonne
        for j in range(0,  self.numCelle_y):
            prec = True
            for i in range(0, self.numCelle_x):
                if prec and not self.matrix[i][j].full:
                    self.matrix[i][j].setcolumnOk()
                    prec = False
                    #se entrambe rispettano le condizioni aggiungo alla lista
                    if self.matrix[i][j].rowOK:
                        if [i,j] not in self.positions:
                            self.positions.append( [i,j] )
                else:
                    if self.matrix[i][j].full:
                        prec = True
                    else:
                        prec= False

    # Metodo che resstituisce la lista di candidate posizioni interne
    def getPositions(self):
        ps = []
        for ind in self.positions:
            ps.append( [mathutils.Vector((ind[0] * self.dimX + self.Low_Left.x, ind[1] * self.dimY + self.Low_Left.y)), ind])
        return ps

    # Stampa della bitmap
    def printMatrix(self):
        for i in reversed(range(0, self.numCelle_x)):
            for j in range(0, self.numCelle_y):
                if self.matrix[i][j].full:
                    c = '##'
                else:
                    c = '__'
                print(c, end='')
            print()

    # Metodo che riempe celle dopo un inserimento interno
    def fillCells(self, c_i, c_j, base, height):
        new_i = c_i + int(base/self.dimX)
        new_j = c_j + int(height/self.dimY)
        
        if new_i > self.numCelle_x:
            new_i = self.numCelle_x 
        if new_j > self.numCelle_y:
            new_j = self.numCelle_y 
        self.fill(c_i, c_j, new_i,  new_j)
        self.findPositions()
        self.positions.remove([c_i,c_j])


    def fill(self, from_x, from_y, to_x, to_y):
        if to_x != self.numCelle_x:
            to_x +=1
        if to_y != self.numCelle_y:
            to_y +=1
        for i in range(from_x, to_x ):
            for j in range(from_y, to_y ):
                self.matrix[i][j].setFull()
                self.fullCells = self.fullCells + 1
        if self.fullCells == self.numCelle_x * self.numCelle_y:
            self.complete = True


    # Aria occupata dalle celle
    def getCellArea(self):
        return (self.numCelle_x * self.numCelle_y)*self.dimX * self.dimY

    # Get dei spigoli
    def bottomEdge(self):
        ris = [self.Low_Left, self.Low_Right]
        return ris

    def leftEdge(self):
        ris = [self.Low_Left, self.Top_Left]
        return ris
        
    def rightEdge(self):
        ris = [self.Low_Right, self.Top_Right]
        return ris
   
    def upperEdge(self):
        ris = [self.Top_Left, self.Top_Right]
        return ris

    # Get Base e altezza
    def base(self):
        return abs(self.Low_Right.x - self.Low_Left.x) 
    
    def height(self):
        return abs(self.Top_Left.y - self.Low_Left.y)

    # Intersezione con altro AABB
    def intersect(self, left, low, right, top):
        _min = mathutils.Vector((left + epsilon,low + epsilon))
        _max = mathutils.Vector((right -epsilon ,top -epsilon))

        if self.Top_Right.x < _min.x  or self.Low_Left.x > _max.x:
            return False
        if self.Top_Right.y < _min.y  or self.Low_Left.y > _max.y:
            return False
        return True

    # Posizionamento
    def posiziona(self, x, y):
        b = self.base()
        h = self.height()
        self.Low_Left  = mathutils.Vector((x , y))        
        self.Top_Right = mathutils.Vector((x + b, y + h))
        self.Low_Right = mathutils.Vector((self.Top_Right.x, self.Low_Left.y))
        self.Top_Left  = mathutils.Vector((self.Low_Left.x, self.Top_Right.y))
        #if self.inside:
        #    Cell.Cell.LL = self.Low_Left

    # Calcolo area del box
    def area(self):
        base = abs(self.Low_Right.x - self.Low_Left.x)
        altezza = abs(self.Top_Left.y - self.Low_Left.y)
        return base * altezza

    # Metodo per confronto area
    def __lt__(self, other):
        base = abs(self.Low_Right.x - self.Low_Left.x)
        altezza = abs(self.Top_Left.y - self.Low_Left.y)
        area = base * altezza 
        base = abs(other.Low_Right.x - other.Low_Left.x)
        altezza = abs(other.Top_Left.y - other.Low_Left.y)
        area2 = base * altezza
        return area < (area2 + 0.0002)

    # Metodo per rappresentazione in stringa
    def __str__(self):
        tostring = str(self.index) + ":" + str(self.Low_Left) + str(self.Low_Right) + str(self.Top_Left) + str(self.Top_Right)
        return tostring 
      
    # Rotazione di 90 gradi
    def ruota(self):
        for face in self.mesh:
            for loop in face.loops:
                loop_uv = loop[self.uv_layer]
                coord_x = loop_uv.uv.x
                coord_y = loop_uv.uv.y
                loop_uv.uv.x = coord_x * math.cos(math.pi/2) - coord_y * math.sin(math.pi/2)
                loop_uv.uv.y = coord_x * math.sin(math.pi/2) + coord_y * math.cos(math.pi/2)
        
        if self.dimX > 0 and self.inside:
            oldMatrix = []
            for i in range(0, self.numCelle_x):
                for j in range (0, self.numCelle_y): 
                    oldMatrix[i][j] = self.matrix[i][j]
        min_ = self.Low_Left 
        min_.x = min_.x * math.cos(math.pi/2) - min_.y * math.sin(math.pi/2)
        min_.y = min_.x * math.sin(math.pi/2) + min_.y * math.cos(math.pi/2)
        max_ = mathutils.Vector((min_.x + self.base() , min_.y + self.base()))
        self.Low_Left  = mathutils.Vector((min_.x , min_.y))
        self.Low_Right = mathutils.Vector((max_.x, min_.y))
        self.Top_Left  = mathutils.Vector((min_.x , max_.y))
        self.Top_Right = mathutils.Vector((max_.x, max_.y))
        
    # Scalamento del box
    def Scale(self, valueX, valueY):
        appMin = self.Low_Left
        appMax = self.Top_Right
        self.Low_Left  = mathutils.Vector((appMin.x * valueX, appMin.y * valueY))
        self.Top_Right = mathutils.Vector((appMax.x * valueX, appMax.y * valueY))
        self.Low_Right = mathutils.Vector((self.Top_Right.x, self.Low_Left.y))
        self.Top_Left  = mathutils.Vector((self.Low_Left.x, self.Top_Right.y))
        self.lastY  = self.lastY  * valueY
        if self.inside:
            self.dimX = self.dimX * valueX
            self.dimY = self.dimY * valueY

    # Trasformazioni finali delle facce dell'isola  
    def conclude(self, value):
        for face in self.mesh:
            for loop in face.loops:
                loop_uv = loop[self.uv_layer]
                vertex = loop_uv.uv.xy
                diff = vertex - self.PosIn
                loop_uv.uv.x = loop_uv.uv.x * value
                loop_uv.uv.y = loop_uv.uv.y * value
                diff.x = diff.x * value
                diff.y = diff.y * value
                loop_uv.uv.x = self.Low_Left.x + self.udim_X + diff.x
                loop_uv.uv.y = self.Low_Left.y + self.udim_Y + diff.y

    # Calcolo dell'area dei triangoli che compongono l'isola
    def covArea(self):
        area = 0
        for face in self.mesh:
            vertices = []
            for loop in face.loops:
                loop_uv = loop[self.uv_layer]
                vertices.append(loop_uv.uv.xy)
            area = area + mathutils.geometry.area_tri(vertices[0], vertices[1], vertices[2])
        return area


    # Calcolo dello score
    def calcolaScore(self, boxes, pos, x, y):
        score = 0
        base = abs(self.Low_Right.x - self.Low_Left.x)
        altezza = abs(self.Top_Left.y - self.Low_Left.y)
        perimetro = base * 2 + altezza * 2

        Low_Left = mathutils.Vector((x, y))
        Low_Right = mathutils.Vector((x + base, y))
        Top_Left = mathutils.Vector((x, y + altezza))
        Top_Right = mathutils.Vector((x + base, y + altezza))
        flag_sotto = False
        flag_lato = False

        if Low_Left.y < self.udim_X - epsilon or Top_Left.y < self.udim_Y - epsilon:
            return -1
        
        if Low_Left.y < self.udim_Y + epsilon and Low_Left.y > self.udim_Y - epsilon:
            score += base
            flag_sotto = True
        if Top_Left.y < self.udim_Y + 1 + epsilon and Top_Left.y > self.udim_Y + 1 - epsilon:
            score += base
        if Low_Left.x < self.udim_X + epsilon and Low_Left.x > self.udim_X - epsilon:
            score += altezza
            flag_lato = True
        if Low_Right.x < self.udim_X + 1 + epsilon and Low_Right.x > self.udim_X + 1 - epsilon:
            score += altezza
        
        for i in pos:
            box = boxes[i]
            position = box.upperEdge()
            vertex_l = mathutils.Vector(position[0])
            vertex_r = mathutils.Vector(position[1])

            if Low_Left.y < vertex_l.y + 0.01 and Low_Left.y > vertex_l.y - epsilon:
                if vertex_l.x > vertex_r.x:
                    app = vertex_r.x
                    vertex_r.x = vertex_l.x
                    vertex_l.x = app
                increm = 0
                
                if vertex_l.x > Low_Left.x - epsilon and vertex_r.x < Low_Right.x + epsilon:
                    increm = abs(vertex_r.x - vertex_l.x)
                    score += increm
                elif vertex_l.x > Low_Left.x - epsilon and vertex_l.x < Low_Right.x + epsilon:
                    increm = abs(Low_Right.x - vertex_l.x)
                    score += increm
                elif vertex_r.x < Low_Right.x + epsilon and vertex_r.x > Low_Left.x - epsilon:
                    increm = abs(vertex_r.x - Low_Left.x)
                    score += increm
                elif Low_Left.x > vertex_l.x and Low_Right.x < vertex_r.x:
                    increm = abs(Low_Right.x - Low_Left.x)
                    score += increm

                

                if increm > epsilon:
                    flag_sotto = True
                
            else:
                position = box.rightEdge()
                vertex_h = mathutils.Vector(position[0])
                vertex_l = mathutils.Vector(position[1])
                if Low_Left.x <vertex_l.x + epsilon and  Low_Left.x > vertex_l.x - epsilon :
                    if vertex_l.y > vertex_h.y:
                        app = vertex_h.y
                        vertex_h.y = vertex_l.y
                        vertex_l.y = app
                    increm = 0
                    if vertex_l.y > Low_Left.y - epsilon and vertex_h.y < Top_Left.y + epsilon:
                        increm = abs(vertex_h.y - vertex_l.y)
                        score += increm
                    elif vertex_l.y > Low_Left.y - epsilon and vertex_l.y < Top_Left.y + epsilon:
                        increm = abs(Top_Left.y  - vertex_l.y)
                        score += increm
                    elif vertex_h.y < Top_Left.y + epsilon and vertex_h.y > Low_Left.y - epsilon:
                        increm = abs(vertex_h.y - Low_Left.y)
                        score += increm
                    elif Low_Left.y > vertex_l.y and Top_Left.y < vertex_h.y:
                        increm = abs(Top_Left.y- Low_Left.y)
                        score += increm
                    if increm > epsilon:
                        flag_lato = True
                    
                else:
                    position = box.leftEdge()
                    vertex_h = mathutils.Vector(position[0])
                    vertex_l = mathutils.Vector(position[1])
                    if Low_Right.x <vertex_l.x + epsilon and  Low_Right.x > vertex_l.x - epsilon :
                        if vertex_l.y > vertex_h.y:
                            app = vertex_h.y
                            vertex_h.y = vertex_l.y
                            vertex_l.y = app
                        if vertex_l.y > Low_Right.y - epsilon and vertex_h.y < Top_Right.y + epsilon:
                            score += abs(vertex_h.y - vertex_l.y)
                        elif vertex_l.y > Low_Right.y - epsilon and vertex_l.y < Top_Right.y + epsilon:
                            score += abs(Top_Right.y  - vertex_l.y)
                        elif vertex_h.y < Top_Right.y + epsilon and vertex_h.y > Low_Right.y + epsilon:
                            score += abs(vertex_h.y - Low_Right.y)
                        elif Low_Right.y > vertex_l.y and Top_Right.y < vertex_h.y:
                            score += abs(Top_Right.y - Low_Right.y)
                    else:
                        position = box.bottomEdge()
                        vertex_l = mathutils.Vector(position[0])
                        vertex_r = mathutils.Vector(position[1])
                        if Top_Left.y < vertex_l.y + epsilon and Top_Left.y > vertex_l.y - epsilon:
                            if vertex_l.x > vertex_r.x:
                                app = vertex_r.x
                                vertex_r.x = vertex_l.x
                                vertex_l.x = app
                            if vertex_l.x > Top_Left.x - epsilon and vertex_r.x < Top_Right.x + epsilon:
                                score += abs(vertex_r.x - vertex_l.x)
                            elif vertex_l.x > Top_Left.x - epsilon and vertex_l.x < Top_Right.x + epsilon:
                                score += abs(Top_Right.x - vertex_l.x)
                            elif vertex_r.x < Top_Right.x + epsilon and vertex_r.x > Top_Left.x + epsilon:
                                score += abs(vertex_r.x - Top_Left.x)
                            elif Top_Left.x > vertex_l.x and Top_Right.x < vertex_r.x:
                                score += abs(Top_Right.x - Top_Left.x)

        
        if not flag_sotto or not flag_lato:
            return -1
        score = score / perimetro
        return score
