"""Presentation-only travel and sensor appearance; no model events or delays."""
TRAVEL_NANOSECONDS=800_000_000

POSITION_BODY='''
double[] route=this.a3d_route;
double progress=Math.max(0,Math.min(1,(System.nanoTime()-this.a3d_startedNs)/800000000.0));
double total=0;
for(int k=2;k<route.length;k+=2) total+=Math.hypot(route[k]-route[k-2],route[k+1]-route[k-1]);
double remaining=total*progress;
for(int k=2;k<route.length;k+=2){
 double length=Math.hypot(route[k]-route[k-2],route[k+1]-route[k-1]);
 if(remaining<=length && length>0){double f=remaining/length;
  return new double[]{route[k-2]+f*(route[k]-route[k-2]),route[k-1]+f*(route[k+1]-route[k-1])};}
 remaining-=length;
}
return new double[]{route[route.length-2],route[route.length-1]};
'''

MOVE_BODY='''
// Keep a just-started rework route when a zero-time service-start changes its endpoint.
if(this.a3d_route.length>4 && System.nanoTime()-this.a3d_startedNs<800000000L && target.length==2){
 this.a3d_route[this.a3d_route.length-2]=target[0];this.a3d_route[this.a3d_route.length-1]=target[1];
 return;
}
double[] current=this.a3d_position.get();
double[] route=new double[target.length+2];route[0]=current[0];route[1]=current[1];
System.arraycopy(target,0,route,2,target.length);
this.a3d_route=route;this.a3d_startedNs=System.nanoTime();
'''


def job_fields():
    return {
      'a3d_route':('double[]','new double[]{160,300,160,300}'),
      'a3d_startedNs':('long','0L'),
      'a3d_shown':('boolean','false'),
      'a3d_phase':('int','0'),
      'a3d_state':('int','0'),
      'a3d_lastStage':('int','-1'),
      'a3d_position':('java.util.function.Supplier<double[]>','null'),
    }


def main_motion_fields():
    # Native code generation rejects these lambda initializers on Job.
    # Main already supports callable presentation hooks, so keep them there.
    position=POSITION_BODY.replace('this.','j.')
    move=MOVE_BODY.replace('this.a3d_position.get()','this.a3d_position.apply(j)')
    move=move.replace('this.a3d_route','j.a3d_route').replace('this.a3d_startedNs','j.a3d_startedNs')
    return {'a3d_position':('java.util.function.Function<Job,double[]>','(j)->{'+position+'}'),
            'a3d_moveTo':('java.util.function.BiConsumer<Job,double[]>','(j,target)->{'+move+'}')}


def shipping_fields():
    body='''double[] p=this.a3d_shipRoutes[slot];
double f=Math.max(0,Math.min(1,(System.nanoTime()-this.a3d_shipStartedNs[slot])/800000000.0));
return new double[]{p[0]+f*(p[2]-p[0]),p[1]+f*(p[3]-p[1])};'''
    return {
      'a3d_shipRoutes':('double[][]','new double[6][4]'),
      'a3d_shipStartedNs':('long[]','new long[6]'),
      'a3d_shipShown':('boolean[]','new boolean[6]'),
      'a3d_shipPosition':('java.util.function.IntFunction<double[]>','(slot)->{'+body+'}'),
    }
