*deck,usermatth                      USERDISTRIB
      subroutine usermatth(matId, elemId, kDomIntPt, kLayer,
     &                     kSectPt, ldstep, isubst, keycut,
     &                     ncomp, nStatev, nProp, Time, dTime,
     &                     Temp, dTemp, tgrad, ustatev, prop,
     &                     coords, dudt, dudg, flux, dfdt,
     &                     dfdg, cutFactor, hgen, dens,
     &                     var1, var2, var3, var4, var5, var6)
c
c     Phenolic pyrolysis plus local outgassing diagnostics.
c
c     Properties in TB,USER (SI units):
c       1  virgin thermal conductivity       [W/(m K)]
c       2  char thermal conductivity          [W/(m K)]
c       3  virgin specific heat               [J/(kg K)]
c       4  char specific heat                  [J/(kg K)]
c       5  virgin density                      [kg/m3]
c       6  char density                        [kg/m3]
c       7  Arrhenius pre-exponential factor A  [1/s]
c       8  activation energy Ea                [J/mol]
c       9  reaction order n                    [-]
c      10  positive pyrolysis enthalpy         [J/kg]
c      11  Celsius-to-Kelvin offset            [K]
c      12  pyrolysis-gas specific heat         [J/(kg K)]
c      13  gas reference temperature           [K]
c      14  gas sensible-energy fraction        [0..1]
c      15  released-gas yield multiplier       [0..1]
c
c     State variables:
c       1  alpha, 0 = virgin and 1 = char
c       2  alpha rate                          [1/s]
c       3  gas mass source                     [kg/(m3 s)]
c       4  cumulative released-gas density     [kg/m3]
c       5  gas sensible-energy sink magnitude  [W/kg]
c
c     Kinetics:
c       d(alpha)/dt = A exp(-Ea/(R T)) (1-alpha)**n
c
c     The reaction is integrated analytically over the current time
c     increment.  All state is local to an integration point, which
c     keeps the routine safe for shared- and distributed-memory solves.
c
      implicit none

      integer matId, elemId, kDomIntPt, kLayer, kSectPt
      integer ldstep, isubst, keycut, ncomp, nStatev, nProp
      integer i, j

      double precision Time, dTime, Temp, dTemp
      double precision tgrad(ncomp), ustatev(nStatev)
      double precision prop(nProp), coords(3)
      double precision dudt, dudg(ncomp), flux(ncomp)
      double precision dfdt(ncomp), dfdg(ncomp,ncomp)
      double precision cutFactor, hgen, dens
      double precision var1, var2, var3, var4, var5, var6

      double precision gasr, minTemp, maxDAlpha, minCut
      parameter (gasr=8.31446261815324d0)
      parameter (minTemp=1.0d0)
      parameter (maxDAlpha=5.0d-2)
      parameter (minCut=1.0d-1)

      double precision kv, kc, cpv, cpc, rhov, rhoc
      double precision apre, ea, ordern, deltaH, tempOffset
      double precision gasCp, gasTref, gasEnergyFrac, gasYield
      double precision temperatureMid, exponent, rateConstant
      double precision alphaOld, alphaNew, alphaDot, deltaAlpha
      double precision betaOld, betaNew, power, bracket
      double precision conductivity, specificHeat, densityNew
      double precision gasMassRate, gasMassCumulative, gasHeatSink
      double precision availableGasDensity, gasDeltaTemperature

c     Always initialize every output controlled by UserMatTh.
      keycut = 0
      cutFactor = 1.0d0
      dudt = 1.0d0
      do i = 1, ncomp
         dudg(i) = 0.0d0
         flux(i) = 0.0d0
         dfdt(i) = 0.0d0
         do j = 1, ncomp
            dfdg(i,j) = 0.0d0
         enddo
      enddo

c     A cutback is safer than accessing an incomplete material table.
      if (nProp .lt. 15 .or. nStatev .lt. 5) then
         keycut = 1
         cutFactor = minCut
         return
      endif

      kv            = prop(1)
      kc            = prop(2)
      cpv           = prop(3)
      cpc           = prop(4)
      rhov          = prop(5)
      rhoc          = prop(6)
      apre          = prop(7)
      ea            = prop(8)
      ordern        = prop(9)
      deltaH        = prop(10)
      tempOffset    = prop(11)
      gasCp         = prop(12)
      gasTref       = prop(13)
      gasEnergyFrac = prop(14)
      gasYield      = prop(15)

c     Reject nonphysical values without allowing NaNs into the solve.
      if (kv .le. 0.0d0 .or. kc .le. 0.0d0 .or.
     &    cpv .le. 0.0d0 .or. cpc .le. 0.0d0 .or.
     &    rhov .le. 0.0d0 .or. rhoc .le. 0.0d0 .or.
     &    rhoc .gt. rhov .or. apre .lt. 0.0d0 .or.
     &    ea .lt. 0.0d0 .or. ordern .le. 0.0d0 .or.
     &    deltaH .lt. 0.0d0 .or. gasCp .lt. 0.0d0 .or.
     &    gasTref .lt. 0.0d0 .or. gasEnergyFrac .lt. 0.0d0
     &    .or. gasEnergyFrac .gt. 1.0d0 .or.
     &    gasYield .lt. 0.0d0 .or. gasYield .gt. 1.0d0) then
         keycut = 1
         cutFactor = minCut
         return
      endif

      alphaOld = dmax1(0.0d0, dmin1(1.0d0, ustatev(1)))
      temperatureMid = Temp + 0.5d0*dTemp + tempOffset
      temperatureMid = dmax1(temperatureMid, minTemp)

      exponent = -ea/(gasr*temperatureMid)
      exponent = dmax1(-700.0d0, dmin1(700.0d0, exponent))
      rateConstant = apre*dexp(exponent)

      alphaNew = alphaOld
      if (dTime .gt. 0.0d0 .and. rateConstant .gt. 0.0d0
     &    .and. alphaOld .lt. 1.0d0) then
         betaOld = dmax1(1.0d0-alphaOld, 0.0d0)
         if (dabs(ordern-1.0d0) .le. 1.0d-10) then
            betaNew = betaOld*dexp(-rateConstant*dTime)
         else
            power = 1.0d0-ordern
            bracket = betaOld**power
     &                - power*rateConstant*dTime
            if (bracket .le. 0.0d0) then
               betaNew = 0.0d0
            else
               betaNew = bracket**(1.0d0/power)
            endif
         endif
         alphaNew = 1.0d0-betaNew
         alphaNew = dmax1(alphaOld, dmin1(1.0d0, alphaNew))
      endif

      deltaAlpha = alphaNew-alphaOld
      alphaDot = 0.0d0
      if (dTime .gt. 0.0d0) alphaDot = deltaAlpha/dTime

c     Linear virgin/char mixture at the updated conversion.
      conductivity = (1.0d0-alphaNew)*kv + alphaNew*kc
      specificHeat = (1.0d0-alphaNew)*cpv + alphaNew*cpc
      densityNew   = (1.0d0-alphaNew)*rhov + alphaNew*rhoc

c     Released gas is the solid density loss associated with conversion.
      availableGasDensity = gasYield*dmax1(rhov-rhoc, 0.0d0)
      gasMassRate = availableGasDensity*alphaDot
      gasMassCumulative = availableGasDensity*alphaNew
      gasDeltaTemperature = dmax1(temperatureMid-gasTref, 0.0d0)
      gasHeatSink = gasEnergyFrac*gasMassRate*gasCp
     &              *gasDeltaTemperature/dmax1(densityNew, 1.0d-30)

      dudt = specificHeat
      dens = densityNew
      do i = 1, ncomp
         flux(i) = -conductivity*tgrad(i)
         dfdg(i,i) = -conductivity
      enddo

      ustatev(1) = alphaNew
      ustatev(2) = alphaDot
      ustatev(3) = gasMassRate
      ustatev(4) = gasMassCumulative
      ustatev(5) = gasHeatSink

c     For pure thermal elements hgen is heat generation per unit mass.
c     Both positive enthalpy terms are sinks, hence the minus signs.
      hgen = hgen-deltaH*alphaDot-gasHeatSink

c     Limit conversion to five percent per accepted increment.
      if (deltaAlpha .gt. maxDAlpha) then
         keycut = 1
         cutFactor = maxDAlpha/dmax1(deltaAlpha, 1.0d-30)
         cutFactor = dmax1(minCut, dmin1(0.95d0, cutFactor))
      endif

      return
      end
