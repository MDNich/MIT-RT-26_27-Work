/BATCH  
/FILNAME,verify_controller,1
/TITLE,Simulation 2 controller verification wedge   
/PREP7  
    
ET,3,278
MP,DENS,3,1250.0
MP,C,3,900.0
MP,KXX,3,0.25   
matid=3 
/INPUT,phenolic_pyrolysis_outgassing,apdl   
    
R0=0.133350 
R1=0.134620 
R2=0.135890 
TH=0.01 
YL=0.050
    
N,1,R0,0,0  
N,2,R1,0,0  
N,3,R1*COS(TH),0,R1*SIN(TH) 
N,4,R0*COS(TH),0,R0*SIN(TH) 
N,5,R0,YL,0 
N,6,R1,YL,0 
N,7,R1*COS(TH),YL,R1*SIN(TH)
N,8,R0*COS(TH),YL,R0*SIN(TH)
N,9,R2,0,0  
N,10,R2*COS(TH),0,R2*SIN(TH)
N,11,R2,YL,0
N,12,R2*COS(TH),YL,R2*SIN(TH)   
    
TYPE,3  
MAT,3   
E,1,2,3,4,5,6,7,8   
E,2,9,10,3,6,11,12,7
FINISH  
    
/SOLU   
ANTYPE,TRANS
TRNOPT,FULL 
TUNIF,926.85
KBC,1   
AUTOTS,ON   
OUTRES,ALL,ALL  
CSYS,5  
SELTOL,1.0E-7   
NSEL,S,LOC,X,R2-1.0E-7,R2+1.0E-7
D,ALL,TEMP,926.85   
CSYS,0  
ALLSEL,ALL  
SIM2_TESTMODE=1 
/INPUT,simulation2_controller,apdl  
    
/EXIT,NOSAVE
