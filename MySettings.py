import bpy


# Classe per le impostazioni personalizzate
exit = False


# Metodi per selezionare solo un checkBox tra Udim e Rescale
def OutOfBounds(self, context):
    obj = context.object
    my_sett = obj.my_sett
    
    global exit
    if not exit:
        exit = True
        print(self)
        if my_sett.Rescale:
            my_sett.Udim = False
        else:
            my_sett.Udim = True
        
    exit = False

def OutOfBounds_1(self, context):
    obj = context.object
    my_sett = obj.my_sett
    global exit
    if not exit:
        exit = True
        if my_sett.Udim:
            my_sett.Rescale = False
        else:
            my_sett.Rescale = True
        
    exit = False

class MySettings(bpy.types.PropertyGroup):
    # CheckBox per attivare il packing interno
    Inside: bpy.props.BoolProperty(name="Pack Inside", description="", default=True)
    # CheckBox per attivare il riscalamento
    Rescale: bpy.props.BoolProperty(name="Rescale", description="Rescales islands when no normal position is found", default=True, update = OutOfBounds)
    # CheckBox per attivare l'Udim
    Udim: bpy.props.BoolProperty(name="UDIM", description="Udim is used when no normal position is found", default=False, update = OutOfBounds_1)
     # CheckBox per attivare la rotazione
    Rotate: bpy.props.BoolProperty(name="Rotate", description="", default=False)
