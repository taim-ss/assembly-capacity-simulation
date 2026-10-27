"""A sensor work-order carrier: parts tray, assembled module, QA seal and carton."""
from . import primitives as P
from .schema import JOB_SHAPE_NAME,shape_expression
PRODUCT_SCALE=0.45  # 20.7 x 14.4 carrier fits 22-unit queues and 35 x 24 service slots


def _pose(shape,dx,dy,dz,visible='true'):
    for key in ('Width','Height','RadiusX','RadiusY','ZHeight'):
        node=shape.find(key)
        if node is not None:node.text=str(float(node.text)*PRODUCT_SCALE)
    dx*=PRODUCT_SCALE;dy*=PRODUCT_SCALE;dz*=PRODUCT_SCALE
    # Cancel any PML agent transform, keeping the visual route in absolute world coordinates.
    for key,expression in [('XCode',f'Job.this.a3d_position==null ? 0 : Job.this.a3d_position.get()[0]-Job.this.getX()+({dx})'),
                           ('YCode',f'Job.this.a3d_position==null ? 0 : Job.this.a3d_position.get()[1]-Job.this.getY()+({dy})'),
                           ('ZCode',f'82-Job.this.getZ()+({dz})')]:
        shape_expression(shape,key,'return '+expression+';')
    shape_expression(shape,'VisibleCode',f'return a3d_shown && ({visible});')
    return shape


def all_job_shapes():
    state='a3d_state==2 ? new java.awt.Color(230,57,70) : (a3d_state==1 ? new java.awt.Color(67,170,139) : new java.awt.Color(87,117,144))'
    base=P.rectangle3d(JOB_SHAPE_NAME,-23,-16,46,32,'#577590',z_height=4,
                       fill_code='return '+state+';',mode='3d')
    out=[_pose(base,-23,-16,0)]
    out.append(_pose(P.rectangle3d('a3d_product_pcb',0,0,30,18,'#15803d',z_height=3,mode='3d'),-15,-9,5,'a3d_phase<4'))
    for i in range(3):
        out.append(_pose(P.rectangle3d(f'a3d_product_chip_{i}',0,0,5,6,'#1e293b',z_height=4,mode='3d'),-11+9*i,-3,8,'a3d_phase==0'))
    out.append(_pose(P.rectangle3d('a3d_product_housing',0,0,28,19,'#dbeafe',z_height=10,mode='3d'),-14,-10,8,'a3d_phase>=1 && a3d_phase<4'))
    out.append(_pose(P.rectangle3d('a3d_product_sensing_tip',0,0,10,5,'#94a3b8',z_height=5,mode='3d'),12,-3,11,'a3d_phase>=1 && a3d_phase<4'))
    out.append(_pose(P.oval3d('a3d_product_qa_seal',0,0,4,4,'#22c55e',z_height=1,mode='3d'),0,0,19,'a3d_phase>=3 && a3d_phase<4'))
    out.append(_pose(P.rectangle3d('a3d_product_carton',0,0,35,25,'#c99861',z_height=20,mode='3d'),-18,-13,4,'a3d_phase>=4'))
    out.append(_pose(P.rectangle3d('a3d_product_carton_label',0,0,14,10,'#ffffff',z_height=1,mode='3d'),-7,-5,25,'a3d_phase>=4'))
    return out


def job_box_shape():
    """Compatibility entry point; use all_job_shapes() for the full product."""
    return all_job_shapes()[0]
