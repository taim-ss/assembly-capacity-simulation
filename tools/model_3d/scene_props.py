"""Illustrative sensor-factory furniture; built-in 3D-only geometry, no logic mutations."""
from . import primitives as P


def _box(name,x,y,width,depth,color,z=0,height=10,visible=None):
    return P.rectangle3d('a3d_prop_'+name,x,y,width,depth,color,z=z,z_height=height,
                         visible_code=visible,mode='3d')


def _disc(name,x,y,radius,color,z=0,height=8):
    return P.oval3d('a3d_prop_'+name,x,y,radius,radius,color,z=z,z_height=height,mode='3d')


def _bench(key,x,color='#d0d9e3'):
    out=[_box(key+'_table',x-72,255,144,92,color,60,10)]
    for i,(dx,dy) in enumerate([(-64,262),(55,262),(-64,332),(55,332)]):
        out.append(_box(f'{key}_leg_{i}',x+dx,dy,9,9,'#65788b',0,60))
    return out


def _parts(key,x):
    out=[]
    for i,(color,dx) in enumerate([('#2b8d68',-52),('#2c74ae',-12),('#a6b6c5',28)]):
        out.append(_box(f'{key}_bin_{i}',x+dx,260,30,28,'#e7c892',70,12))
        out.append(_box(f'{key}_part_{i}',x+dx+7,265,16,14,color,83,5))
    return out


def _incoming(x):
    out=[_box('incoming_pallet',x-73,260,146,86,'#c5a575',0,12)]
    for i in range(3):
        out.append(_box(f'incoming_tray_{i}',x-61+i*42,268,34,62,'#cda96b',12,28))
        for j in range(2):
            out.append(_box(f'incoming_component_{i}_{j}',x-55+i*42,276+j*25,
                            21,15,['#25886a','#387caf','#b1c1cd'][i],41,5))
    return out


def _assembly(x):
    return _bench('assembly',x,'#c7d5e7')+[
        _box('assembly_housing',x-53,260,38,24,'#a8b6c3',70,10),
        _box('assembly_pcb',x-48,264,28,15,'#277c53',81,3),
        _disc('assembly_probe',x+26,269,7,'#c3cdd5',71,20),
        _box('assembly_tool_rack',x+45,259,14,44,'#536a80',70,30)]


def _test(x):
    return _bench('test',x,'#edd8c1')+[
        _box('test_console',x-62,242,42,15,'#334b60',70,57),
        _box('test_screen',x-58,240,34,2,'#142a3d',89,31),
        _box('test_fixture',x+13,258,44,32,'#73899b',70,8),
        _disc('test_contact_0',x+23,271,3,'#d4bb58',78,15),
        _disc('test_contact_1',x+46,271,3,'#d4bb58',78,15)]


def _quality(x):
    return _bench('quality',x,'#ece3bc')+[
        _box('quality_mat',x-56,260,70,43,'#dce8e0',70,2),
        _box('quality_clipboard',x+31,262,28,35,'#f7fafc',70,3),
        _box('quality_lamp_base',x-55,318,18,18,'#617c8c',70,6),
        _disc('quality_lamp_stem',x-46,326,3,'#617c8c',76,35),
        _disc('quality_lamp_head',x-46,326,12,'#e8ecdd',111,6)]


def _packing(x):
    return _bench('packing',x,'#d4e4cc')+[
        _box('packing_carton',x-59,261,42,32,'#cda672',70,23),
        _box('packing_carton_label',x-49,259,23,2,'#ffffff',77,11),
        _box('packing_flat_cartons',x+16,260,46,35,'#c09a66',70,6),
        _disc('packing_tape',x+42,321,9,'#b6cbd3',71,7)]


def _shipping(x):
    # Actual product agents form the last-six-completed display, owned by motion hooks.
    out=[_box('shipping_pallet',x-73,260,146,86,'#c5a575',70,12),
         _box('shipping_rail_0',x-72,255,144,5,'#b39060',82,5),
         _box('shipping_rail_1',x-72,345,144,5,'#b39060',82,5)]
    for i,(dx,dy) in enumerate([(-64,267),(55,267),(-64,330),(55,330)]):
        out.append(_box(f'shipping_support_{i}',x+dx,dy,9,9,'#65788b',0,70))
    return out


def for_station(station):
    x=station.x
    if station.key=='dock':return _incoming(x)
    if station.key=='kitting':return _bench('kitting',x,'#cadfe9')+_parts('kitting',x)
    return {'assembly':_assembly,'test':_test,'quality':_quality,
            'handover':_packing,'ship':_shipping}[station.key](x)
