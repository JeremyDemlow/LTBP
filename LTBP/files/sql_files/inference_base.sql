-- base EDEE team guest behavior
  with edee_base as (
      SELECT 
            distinct ECID
      from BIDE_EDWDB_CUSTOMERMART_PROD.DBO.CustomerPASSPURCHASEBEHAVIOR cla
      where 
              cla.GuestPassPurchaseBehaviorDetailLabel <> 'Unknown'
  ),

  -- pass prospects not in guest behavior
  prospects as (
      Select
            distinct ECID
      from Vail_Reporting.Prod.GuestBehaviorBase
      where 
              GuestBehavior = 'Prospect'
          and salesseason = '2021/22'
  ),

  -- paid prospects not in guest behavior
  other_scans as (
      select
            distinct a.ECID
      from
      (
          select 
                distinct ECID
              , SeasonYear
          from "BIDE_EDWDB_ARA_PROD"."DBO"."SCANDAY"
              where Season = 'Winter'
      ) a
      left join Vail_Reporting.Prod.GuestBehaviorBase b 
          on a.ECID = b.ECID and a.SeasonYear = b.SalesSeason
      where 
              b.GuestBehavior is null
          and a.seasonyear = '2021/22'
  )

  select
        distinct ECID
      , 'Inference Set' as SeasonYear
  from
  (
      select
            coalesce(base.ecid, pro.ecid, os.ecid) as ecid
      from edee_base base
      full outer join prospects pro
          on pro.ecid = base.ecid
      full outer join other_scans os
          on os.ecid = base.ecid
  ) a