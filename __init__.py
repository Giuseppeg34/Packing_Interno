import bpy
import bmesh
import mathutils
import math
import copy
import time
from collections import defaultdict
from dataclasses import dataclass
from . import  Bounding_Box
from . import MySettings
from . import QuadTreeNode


bl_info = {
    "name" : "PackBboxv5",
    "author" : "Giuseppe",
    "description" : "",
    "blender" : (2, 80, 0),
    "version" : (0, 0, 1),
    "location" : "IMAGE_EDITOR",
    "warning" : "",
    "category" : "PackUV"
}

# Costante epsilon
epsilon = 0.0001

# Dizionario che ha come chiave l'indice della faccia e come elementi i vertici della faccia
faceToVertices = defaultdict(set)
# Dizionario che ha come chiave il vertice e come elementi le facce che lo condividono
vertexToFaces = defaultdict(set)


def completeIsland(faces, faceIndex, faceIndices, island, minmax):
        connectedFaces = []
        connectedFaces.append(faceIndex)
        # Finchè ci sono facce connesse
        while connectedFaces:
            # Si prende la prima faccia della lista
            cface = connectedFaces[0]
            connectedFaces.remove(cface)
            # Se non è stata ancora analizzata
            if cface in faceIndices:
                # Si rimuove dalla lista degli indici
                faceIndices.remove(cface)
                # Si aggiunge all'isola
                island.append(faces[cface])
                # Dizionario con vetici associati alla faccia
                vertices = set(faceToVertices[cface])
                

                del faceToVertices[cface]
                # Finchè c'è qualcosa nel dizionario
                while len(vertices) > 0:
                    # Primo vertice nel dizionario
                    v = list(vertices)[0]
                    #global minmax
                    if v[0][0] > minmax[2]:
                       minmax[2] = v[0][0]
                    if v[0][0] < minmax[0]:
                       minmax[0] = v[0][0]
                    if v[0][1] > minmax[3]:
                      minmax[3] = v[0][1]
                    if v[0][1] < minmax[1]:
                       minmax[1] = v[0][1]
                    #print(minmax)
                    # Si rimuove
                    vertices.remove(v)
                    for f in vertexToFaces[v]:
                        # Si aggiunge alla lista delle facce collegate
                        connectedFaces.append(f)
                    del vertexToFaces[v]

# Struttura per memorizzare lo score e relativa posizione
@dataclass
class Score_struct:
    # Punteggio
    score: float
    # Coordinate
    coord_x: float
    coord_y: float
    # Scarto
    difference: float
    # Direzione in cui fuorisce il box (se True asse u)
    scale_oriz: bool
    # Orientazione
    orientV: bool
    # Indice dell'elemento adiacente
    index: int
    # Se inserito in cima
    top: bool
    
    def __lt__(self, other):
         return self.score < other.score + epsilon



class PackBoxInsideOperator(bpy.types.Operator): 
    """Esegui Pack"""
    # Nome operatore
    bl_idname = "uv.packboxinside_operator"
    bl_label = "Pack Box"
 

    # Variabili per il calcolo del tempo
    ScoreTime = 0.0
    AdjTime = 0.0
    CollisionTime = 0.0
    # Valore totale di scala applicato
    totAlpha = 1
    # Lista di quadtree, uno per ogni tile
    QuadTree = []
    
    # Ultimo indice su cui è stata fatta la rasterizzazione
    maxIndexInside = -1
    # Lista elementi posizionati
    posizionati = []
    # Coordinate Udim dell'ultimo tile
    MaxUdim_x = 0
    MaxUdim_y = 0

    max = 0
    max_l = 0
    minmax = [0,0,0,0]

    # Creazione dei BBox:
    #   Per ogni faccia -> si selezionano le facce collegate e si aggiungono ad una lista
    #   Si crea il BBox passando la lista di facce trovando i punti minX, minY, maxX, maxX con una scansione dei vertici delle facce
    def createBBox(self, faces, uv_layer, my_sett): 
        Boxes = []
        c = 0
        margin = my_sett.Margin
        
        for face in faces:
            # Per ogni loop della faccia
            for loop in face.loops:
                # Si salvano le coordinate del vertice e l'indice (per evitare che si confonda con altri sovrapposti)
                vertex = loop[uv_layer].uv.to_tuple(4), loop.vert.index
                # Si aggiunge alla chiave [indice della faccia] il vertice
                faceToVertices[face.index].add(vertex)
                # Si aggiunge alla chiave [vertice] l'indice della faccia
                vertexToFaces[vertex].add(face.index)

        # Indici delle facce
        faceIndices = set(faceToVertices.keys())
        # Finchè c'è qualcosa nel dizionario
        while len(faceIndices) > 0 :
            # Lista di facce dell'isola attuale
            island = []
            # Primo elemento nel dizionario di facce
            faceIndex = list(faceIndices)[0]
            #global minmax
            minmax = [0,0,0,0]
            minmax[0]=10
            minmax[1]=10
            minmax[2]=-10
            minmax[3]=-10
            # Si completa l'isola aggiungendo le facce collegate
            completeIsland(faces, faceIndex, faceIndices, island, minmax)
            
            # Si aggiunge alla lista delle isole
            new = Bounding_Box.Bounding_Box(island, uv_layer, c, margin, mathutils.Vector((minmax[0], minmax[1])), mathutils.Vector((minmax[2], minmax[3])))
            #new.scanline()
            c += 1
            Boxes.append(new)
        return Boxes

    # Metodo che ordina gli oggetti in base all'area e li orienta orizzontalmente se attivo il flag ruota
    # Se "inside" è true -> si crea la matrice con rasterizzazione dei triangoli
    def sort_and_rotate(self, boxes, ruota, inside, bm):
        newBoxes = boxes[:]
        # Ordinamento isole
        newBoxes.sort(reverse=True)
        boxesIndex = []
        for box in newBoxes:
            boxesIndex.append(box.index)
        
        # Se attivo il flag ruota, orienta gli AABB orizzontalemente
        if ruota:
            for box in boxes:
                if box.base() < box.height():
                    box.ruota()

        # Se attivo il flag inside, crea le bitmap dell'isola
        tot = 0
        if inside:
            for i in boxesIndex:
                box = boxes[i]
                if box.height() < 0.05 and box.base() < 0.05:
                    self.maxIndexInside = i
                    break
                tot = tot + box.rasterize() 
        return boxesIndex

    # Metodo che scala preventivamente le isole
    def scale(self, boxes, inside):
        areaTot = 0
        for box in boxes:
            if not inside:
                areaTot = areaTot + box.area()
            else:
                areaTot = areaTot + box.getCellArea()
        if areaTot > 1:
            alpha = math.sqrt(1 / areaTot)
            self.totAlpha = self.totAlpha * alpha
            for box in boxes:
                box.Scale(alpha, alpha)

    # Metodo che verifica l'intersezione con i box già posizionati e restituisce quello più vicino
    # modifica poi i valori del box adiacente
    def intersectBox(self, boxes, quadList, min, max, soglia, box_index):
        minIntersect = 10
        intersectIndex = -1
        for i in quadList:
            if i != box_index:
                box = boxes[i]
                if box.intersect(min.x + epsilon, min.y + epsilon, max.x, max.y):
                    if box.Low_Left.x > boxes[box_index].Low_Right.x - epsilon and box.Low_Left.x < boxes[box_index].Low_Right.x + epsilon:
                        boxes[box_index].lastY = box.Top_Right.y
                        if boxes[box_index].lastY > boxes[box_index].Top_Right.y:
                            boxes[box_index].totFull = True
                            if boxes[box_index].topComplete:
                                self.posizionati[box.udim_Y * 10 +  box.udim_X].remove(box_index)
                                
                    if box.Top_Right.y > soglia:
                        intersectIndex = -2
                        break
                    if box.Low_Left.y < minIntersect:
                        minIntersect = box.Low_Left.y
                        intersectIndex = i

        return intersectIndex
    
    # Metodo che verifica se c'è intersezione
    def intersect(self, boxes, quadList, min, max, box_index):
        for i in quadList:
            if i != box_index:
                box = boxes[i]
                if box.intersect(min.x, min.y + epsilon, max.x, max.y):
                    return True

        return False

    # Metodo per rilevare la posizione normale con lo score più alto
    def normalPosition(self, boxes, posizionati, QuadTree, base, height, index):
        Max_score = Score_struct(0,0,0,10, False, False, -1, False)
        # Se non c'è nessun elemento posizionato si inserisce il box in 0,0
        # Verificando che entri nel bin
        if posizionati == []:
            point = mathutils.Vector((0, 0))
            if (point.x + base > 1) or (point.y + height > 1):
                diff_x = base - 1
                diff_y = height - 1
                if diff_x > 0 and diff_y > 0:
                    if diff_x > diff_y:
                        Max_score.scale_oriz = True
                    else:
                        Max_score.scale_oriz = False
                elif diff_x > 0:
                    Max_score.scale_oriz = True
                elif diff_y > 0:
                    Max_score.scale_oriz = False
            else:
                Max_score.score = 1 
        else:
            # Altrimenti si scansionano tutti gli elementi posizionati
            for i in posizionati:  
                box = boxes[i]
                # Se il box permette di posizionare un altro box in una posizione adiacente
                if not box.totFull:
                    # Si calcola la prima candidata posizione
                    minBox = box.Low_Left
                    maxBox = box.Top_Right
                    if box.lastY == -1:
                        y = minBox.y - height + epsilon
                    else:
                        y = box.lastY
                    if y < 0:
                        y = 0
                    point = mathutils.Vector((maxBox.x, y))

                    Exit = False
                    while not Exit:
                        # Se il punto è superiore al box si esce dal ciclo
                        if point.y > box.Top_Right.y:
                            break
                        # Si ottiene la lista dei possibili box che possono collidere, si calcola poi l'interesezione
                        quadList = QuadTree.collide(point.x - 2 * epsilon, point.y - 2 * epsilon, point.x + base, point.y + height)
                        intersectIndex = self.intersectBox(boxes, quadList, point, mathutils.Vector((point.x + base, point.y + height)), box.Top_Right.y, i)

                        # Se il punto è superiore al box si esce dal ciclo
                        if intersectIndex == -2:
                            Exit  = True
                        # Se non si intersecano box si verifica lo score
                        elif intersectIndex == -1:
                            # Se fuoriesce dal bin si calcola lo scarto verificando su quale direzione
                            if ((point.x + base > 1) or (point.y + height > 1)):
                                if Max_score.score == 0:
                                    diff_x = point.x + base - 1
                                    diff_y = point.y + height - 1
                                    if diff_x > 0 and diff_y > 0:
                                        diff = 0
                                        if diff_x > diff_y:
                                            diff = diff_x
                                            orient= True
                                        else:
                                            diff = diff_y
                                            orient = False
                                        if diff < Max_score.difference:
                                            Max_score.scale_oriz = orient
                                            Max_score.difference = diff
                                            Max_score.coord_x = point.x
                                            Max_score.coord_y = point.y
                                            Max_score.index = i
                                            Max_score.top = False
                                    elif diff_x > 0 and diff_x < Max_score.difference:
                                        Max_score.difference = diff_x
                                        Max_score.coord_x = point.x
                                        Max_score.coord_y = point.y
                                        Max_score.scale_oriz = True
                                        Max_score.index = i
                                        Max_score.top = False
                                    elif diff_y > 0 and diff_y < Max_score.difference:
                                        Max_score.difference = diff_y
                                        Max_score.coord_x = point.x
                                        Max_score.coord_y = point.y
                                        Max_score.scale_oriz = False
                                        Max_score.index = i
                                        Max_score.top = False
                                Exit = True
                            # Altrimenti si calcola lo score e si verifica se maggiore
                            else:
                                parz_score = boxes[index].calcolaScore(boxes, quadList, point.x , point.y)
                                if parz_score != -1:
                                    if Max_score.score < parz_score: 
                                        Max_score.score   = parz_score
                                        Max_score.coord_x = point.x
                                        Max_score.coord_y = point.y
                                        Max_score.index = i
                                        Max_score.top = False
                                    Exit = True
                            point.y = point.y + 0.1
                        # Se interseca un box si calcola la nuova Y
                        else:
                            point.y = boxes[intersectIndex].Top_Right.y
                # Se possibile inserire un box sopra e se la distanza è minore della base
                if not box.topComplete and (base > box.Low_Left.x):
                    # Si verifica intersezione
                    point = mathutils.Vector((0, box.Top_Right.y))
                    quadList = QuadTree.collide(point.x , point.y, point.x + base , point.y + height )
                    inter = self.intersect(boxes, quadList, point, mathutils.Vector((point.x + base, point.y + height)), i)
                    # Se non c'è si calcola lo score e si verifica se maggiore
                    if not inter:
                        parz_score = boxes[index].calcolaScore(boxes, quadList, point.x, point.y)                        
                        if (base > box.Low_Left.x):
                            if (point.x + base > 1) or (point.y + height > 1):
                                if Max_score.score == 0:
                                    diff_x = point.x + base - 1
                                    diff_y = point.y + height - 1
                                    if diff_x > 0 and diff_y > 0:
                                        diff = 0
                                        if diff_x > diff_y:
                                            diff = diff_x
                                            orient= True
                                        else:
                                            diff = diff_y
                                            orient = False
                                        if diff < Max_score.difference:
                                            Max_score.scale_oriz = orient
                                            Max_score.difference = diff
                                            Max_score.coord_x = point.x
                                            Max_score.coord_y = point.y
                                            Max_score.index = i
                                            Max_score.top = True
                                    elif diff_x > 0 and diff_x < Max_score.difference:
                                        Max_score.difference = diff_x
                                        Max_score.coord_x = point.x
                                        Max_score.coord_y = point.y
                                        Max_score.scale_oriz = True
                                        Max_score.index = i
                                        Max_score.top = True
                                    elif diff_y > 0 and diff_y < Max_score.difference:
                                        Max_score.difference = diff_y
                                        Max_score.coord_x = point.x
                                        Max_score.coord_y = point.y
                                        Max_score.scale_oriz = False
                                        Max_score.top = True
                                        Max_score.index = i
                            else:
                                if parz_score != -1:
                                    if Max_score.score < parz_score: 
                                        Max_score.score   = parz_score
                                        Max_score.coord_x = point.x
                                        Max_score.coord_y = point.y
                                        Max_score.index = i
                                        Max_score.top = True
        # Restituisce la posizione con lo score maggiore
        return Max_score

    # Metodo che verifica intersezione tra BBox e celle piene
    def VerificaCelle(self, x, y, box, otherbox):
        # Dimensioni bic da inserire
        matrix_min = mathutils.Vector((x + 0.000001,y + 0.000001))
        matrix_max = mathutils.Vector((x + box.base(),y + box.height()))
        # Se non si interseca si restituisce falso
        if x + box.base() > otherbox.Low_Left.x + otherbox.base():
            return False
        if y + box.height() > otherbox.Low_Left.y + otherbox.height():
            return False
        # Si calcolano gli indici corrispondenti al buonding box dell'oggetto da inserire
        start_x = int((matrix_min.x - otherbox.Low_Left.x)/otherbox.dimX)
        start_y = int((matrix_min.y - otherbox.Low_Left.y)/otherbox.dimY) 
        end_x   = int((matrix_max.x - otherbox.Low_Left.x)/otherbox.dimX)
        end_y   = int((matrix_max.y - otherbox.Low_Left.y)/otherbox.dimY)
        #Lista celle intersecate
        ListaCelle = []
        # Per ogni cella in quel range si verifica l'intersezione
        for i in range(start_x, end_x):
            for j in range(start_y, end_y):
                cell =  otherbox.matrix[i][j]
                if cell.full:
                    if cell.intersectBox(matrix_min, matrix_max, otherbox.Low_Left, otherbox.dimX, otherbox.dimY):
                        ListaCelle.append(cell)
        # Se la lista è vuota non c'è intersezione
        if ListaCelle == []: 
            return False     
        # Altrimenti si verifica intersezione con celle piene    
        else:
            for i in range(0, box.numCelle_x):
                for j in range(0, box.numCelle_y):
                    cell =  otherbox.matrix[i][j]
                    if cell.full:
                        # Si calcolano i valori min e max della cella
                        cell_min = mathutils.Vector((box.Low_Left.x (i *  box.dimX), box.Low_Left.y (j *  box.dimY)))
                        cell_max = mathutils.Vector((cell_min.x + box.dimX, cell_min.y + box.dimY))
                        # Se c'è intersezione restituisce Vero
                        if cell.intersectBox(cell_min, cell_max, otherbox.Low_Left, otherbox.dimX, otherbox.dimY):
                            return True
            # Se non avviene nessuna intersezione restituisce Falso
            return False
        
    # Metodo che controlla se si è in modalità mesh e in edit mode
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.mode == 'EDIT'

    # Metodo che viene eseguito se si preme il relativo bottono
    def execute(self, context):
        # Variabile per il calcolo del tempo d'esecuzione
        start = time.time()
        # Oggetto attivo
        obj = context.active_object
        # Dati dell'oggeto
        me = obj.data 
        # Dati Bmesh
        bm = bmesh.from_edit_mesh(me) 
        # Livello uv       
        uv_layer = bm.loops.layers.uv.verify()
        # Variabile per verificare quali opzioni sono selezionate
        my_sett = obj.my_sett

        # Variabile per rotazione
        ruota = my_sett.Rotate
        # Variabile per packing interno
        inside = my_sett.Inside

        # Lista oggetti posizionate
        self.posizionati = []
        # Lista dei box ordinata
        SortBoxes = []

        # Creazione Bounding Box e isole 
        CreaIn = time.time()
        Boxes = self.createBBox(bm.faces, uv_layer, my_sett)
        CreaFin = time.time()

        # Ordinamento e rasterizzazione
        SLin = time.time()
        SortBoxes = self.sort_and_rotate(Boxes, ruota, inside, bm)
        SLfin = time.time()

        # Se flag attivo, si verifica se è necessario scalare preventivamente le isole
        if my_sett.Rescale:
            self.scale(Boxes, inside)

        # Variabili per il calcolo parziale del tempo computazionale
        findPosTime = 0
        RescaleTime = 0
        insideTime = 0

        # Se inside True si inizalizza lista dei box rasterizzati
        if inside:
            insideList = []
            stopInside = False


        # Creazione del quadTree
        self.QuadTree = []
        self.QuadTree.append([])
        self.QuadTree[0] = QuadTreeNode.QuadTreeNode(0, 0, 1, 1, 0)
        self.posizionati.append([])

        print("Numero isole",len(SortBoxes))

        # Per ogni AABB ordinato
        for i in SortBoxes:
            
            box = Boxes[i]
            interno = False

            # Se attivo il flag inside si verifica se è possibile inserire l'isola in una di quelle già posizionate
            if inside:
                FindIN = time.time()
                for j in insideList:
                    # Se j è il primo elemento da non rasterizzare esce dal ciclo
                    if j == self.maxIndexInside:
                        break
                    
                    cellBox = Boxes[j]
                    if cellBox.height() < box.height() or cellBox.base() < box.base():
                        break
                    # Se il box non è pieno
                    if not cellBox.complete:
                        # Lista di candidate posizioni
                        positions = cellBox.getPositions()
                        for p in positions:
                            pos = p[0]
                            # Verifica l'intersezione con le celle piene
                            collideInside = self.VerificaCelle(pos.x, pos.y, box, cellBox)
                            # Se non c'è collisione
                            if not collideInside:      
                                # Inserisce nella posizione attuale             
                                box.posiziona(pos.x, pos.y)
                                # Inserimento nello stesso tile del box già posizionato
                                box.udim_X = cellBox.udim_X
                                box.udim_Y = cellBox.udim_Y
                                # Riempie le celle occupate da nuovo box
                                cellBox.fillCells( p[1][0], p[1][1], box.base(), box.height())
                                interno = True
                                break
                    if interno:
                        break
                FindFIN = time.time()
                insideTime = insideTime + round(FindFIN - FindIN, 2)

            # Se non è stata inserita o se il flag inside è disattivato, esegue il TP classico
            if not interno :
                FindIN = time.time()
                finalUdim = -1
                Max_score = Score_struct(0,-1, -1, 10, False, False, -1, False)
                # Per ogni tile attivo, si calcola la posizione normale e si verifica quale ha lo score maggiore
                for udim in range(0, self.MaxUdim_y * 10 + self.MaxUdim_x + 1 ):
                    parz_score = self.normalPosition(Boxes, self.posizionati[udim], self.QuadTree[udim], box.base(), box.height(), box.index)
                    if parz_score.score > Max_score.score:
                        Max_score = parz_score
                        finalUdim = udim

                # Calcolo coordinate del tile trovato        
                if finalUdim != -1:
                    box.udim_Y = (int) (finalUdim/10)
                    box.udim_X = (int) (finalUdim%10)
                FindFIN = time.time()
                findPosTime = findPosTime + round(FindFIN - FindIN, 2)

                # Se lo score è = 0 non è stata trovata alcuna posizione-> necessario scalamento o apertura di un nuovo bin
                if Max_score.score == 0:
                    # Riscalamento
                    if my_sett.Rescale:
                        RescaleTimeIn = time.time()
                        xo = 0
                        if Max_score.scale_oriz:
                            xo = Max_score.coord_x
                            base = box.base()
                        else:
                            xo = Max_score.coord_y
                            base = box.height()
                        
                        # Calcolo del fattore di scala
                        if (base + xo) == 0:
                            alpha = 1
                        else:
                            alpha = 1/(base + xo)
                        self.totAlpha = self.totAlpha * alpha

                        # Scalamento di tutti gli oggetti
                        for j in SortBoxes:
                            app = Boxes[j].Low_Left
                            Boxes[j].Scale(alpha,alpha)
                            Boxes[j].posiziona(app.x * alpha, app.y * alpha)
                            
                        # Aggiornamento del quadTree
                        self.QuadTree[0] = QuadTreeNode.QuadTreeNode(0, 0, 1, 1, 0)
                        finalUdim = 0
                        for k in SortBoxes:
                            if k == i:
                                break
                            quadBox = Boxes[k]
                            self.QuadTree[0].insert(quadBox)

                        # Calcolo posizione aggiornata
                        Max_score.coord_x = Max_score.coord_x * alpha
                        Max_score.coord_y = Max_score.coord_y * alpha
                        RescaleTimeFin = time.time()
                        RescaleTime = RescaleTime + round(RescaleTimeFin - RescaleTimeIn,2)

                    #UDIm
                    else:
                        # Apertura del nuovo tile
                        if self.MaxUdim_x == 9:
                            self.MaxUdim_x = 0
                            self.MaxUdim_y = self.MaxUdim_y + 1
                            if self.MaxUdim_y == 9:
                                Max_score.coord_x = -1.0
                                Max_score.coord_y = -1.0
                                print("ERRORE! SPAZIO UDIM FINITO")
                        else:
                            self.MaxUdim_x = self.MaxUdim_x + 1
                        box.udim_X = self.MaxUdim_x
                        box.udim_Y = self.MaxUdim_y
                        finalUdim = self.MaxUdim_y *10 + self.MaxUdim_x
                        Max_score.coord_x = 0.0
                        Max_score.coord_y = 0.0
                        # Creazione del nuovo quadTree corrispondente al tile
                        self.QuadTree.append(QuadTreeNode.QuadTreeNode(0, 0, 1, 1, 0))
                        self.posizionati.append([])
                 
                # Posizionamento nella posizione trovata
                box.posiziona(Max_score.coord_x, Max_score.coord_y)

                # Verifica delle ottimizzazioni:
                # Se parte superiore completa
                if Max_score.top:
                    Boxes[Max_score.index].topComplete = True
                # Se parte adiacente completa
                if Boxes[Max_score.index].Top_Right.y < box.Top_Right.y and not Max_score.top:
                    Boxes[Max_score.index].totFull = True
                # Ultimo valore y inserito
                elif Boxes[Max_score.index].lastY < box.Low_Left.y and box.Low_Left.y - Boxes[Max_score.index].lastY < 0.1 and not Max_score.top:
                    Boxes[Max_score.index].lastY = box.Top_Right.y
                # Se pieno superiormente e adiacente a destra si rimuove dalla lista
                if  Boxes[Max_score.index].totFull and Boxes[Max_score.index].topComplete:
                    self.posizionati[finalUdim].remove(Max_score.index)
                
                # Inserimento nel QuadTree corrispondente
                self.QuadTree[finalUdim].insert(box)
            
                # Inserimento nella lista di isole già posizionate
                self.posizionati[finalUdim].append(i)

            # Se attivo il packing interno si aggiunge alla lista degli ogggeti rasterizzati
            if inside and not stopInside:
                if i == self.maxIndexInside:
                    stopInside = True
                insideList.append(i)

        # Aggiornaemento delle facce delle isole
        a = time.time()
        area = 0
        for i in SortBoxes:
            Boxes[i].conclude(self.totAlpha)
            # Calcolo area coperta
            area = area + Boxes[i].covArea()
        b = time.time()
        RescaleTime = b - a
        stop = time.time()

        # Stampa dei dati
        if my_sett.Rescale:
            # Fattore di scala totale
            print("Rescale Value:", round(self.totAlpha,3))

        print("Covered area:           ", round(area*100, 2),"%")

        # Tempo per la creazione dell'AABB
        print("Create box:             ", round(CreaFin - CreaIn, 2),"s")

        if inside:
            # Tempo per la creazione delle discretizzazioni
            print("Sort and ScanLine:      ", round(SLfin - SLin, 2),"s")
            # Tempo per il packing all'interno di altre isole
            print("Pack Inside:            ", round(insideTime,2),"s")
        else:
            print("Sort:                   ", round(SLfin - SLin, 2),"s")
        # Tempo per la ricerca della posizione normale
        print("Touching Perimeter:     ", round(findPosTime,2),"s")

        # Tempo per le trasformazioni geometriche
        print("Trasformation:  ", round(RescaleTime,2),"s")
        
        # Tempo totale
        print("Packing Time:", round(stop - start,2),"s\n")
        return {'FINISHED'}




# Pannello
class PackBboxInside(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Pack Box Panel Inside"
    bl_idname = "OBJECT_PT_packpanelInside"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'PackUV'
    
    
    def draw(self, context):
        layout = self.layout
        
        obj = context.object
        my_sett = obj.my_sett

        # Check box packing interno
        row = layout.row()
        row.prop(my_sett, 'Inside')

        # Checkbox riscalamento e Udim
        row = layout.row()
        row.prop(my_sett, 'Rescale')
        row.prop(my_sett, 'Udim')
        
        # Checkbox rotate
        row = layout.row()
        row.prop(my_sett, 'Rotate')

        # Operatore per avviare il packing
        row = layout.row()
        row.operator('uv.packboxinside_operator')
        

def register():
    bpy.utils.register_class(PackBboxInside)
    bpy.utils.register_class(PackBoxInsideOperator)
    bpy.utils.register_class(MySettings.MySettings)
    bpy.types.Object.my_sett = bpy.props.PointerProperty(type=MySettings.MySettings)

    
def unregister(): 
    bpy.utils.unregister_class(PackBboxInside)
    bpy.utils.unregister_class(PackBoxInsideOperator)
    bpy.utils.unregister_class(MySettings.MySettings)
    del bpy.types.Object.my_sett

    
if __name__ == "__main__":
    register()
