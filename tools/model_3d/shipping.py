"""Persistent Main presentation sprites survive Sink's deletion of the process Job."""
from . import primitives as P
from .schema import shape_expression


def sprites():
    out=[]
    for slot in range(6):
        for kind,dx,dy,width,height,z,depth,color in [
            ('carrier',-11,-8,22,16,82,2,'#2b9348'),
            ('carton',-9,-6,18,12,84,10,'#c99861'),
            ('label',-4,-3,8,6,95,1,'#ffffff')]:
            shape=P.rectangle3d(f'a3d_shipping_{slot}_{kind}',0,0,width,height,color,
                               z=z,z_height=depth,mode='3d')
            for key,expression in [('XCode',f'a3d_shipPosition.apply({slot})[0]+({dx})'),
                                   ('YCode',f'a3d_shipPosition.apply({slot})[1]+({dy})'),
                                   ('VisibleCode',f'a3d_shipShown[{slot}]')]:
                shape_expression(shape,key,'return '+expression+';')
            out.append(shape)
    return out
