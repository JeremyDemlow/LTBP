select
distinct fs.ECID as ecid,
dd.SeasonYear as SeasonYear
from BIDE_EDWDB_ARA_PROD.dbo.FactScan fs
left join BIDE_EDWDB_ARA_PROD.dbo.DimDateSeason dd
on dd.DateSeasonKey = fs.DateSeasonKey
where
dd.SeasonYear in ('2018/19')
and fs.IsEmployee = 0
and dd.Season = 'Winter'
LIMIT 10000
