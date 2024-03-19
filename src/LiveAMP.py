from setup import *
db = Oracle('WFOCUSP')
root_path = pathlib.Path("/home/scook/institutional_data_analytics/admitted_matriculation_projection")

def dt(date, format='sql'):
    try:
        date = pd.to_datetime(date).date()
    except:
        return f"trunc({date})"
    format = format.lower()
    if format == 'sql':
        d = date.strftime('%d-%b-%y')
        return f"trunc(to_date('{d}'))"
    elif format == 'iso':
        return date.isoformat()
    else:
        return date.strftime(format)

def get_desc(nm, alias=None):
    tbl = 'stv'+nm if alias is None else 'stv'+alias
    return [f"A.{nm}_code", f"(select B.{tbl}_desc from {tbl} B where B.{tbl}_code = A.{nm}_code) as {nm}_desc"]

#################################### FLAGS ####################################

@dataclasses.dataclass
class FLAGS(MyBaseClass):
    def __post_init__(self):
        self.path = dict()
        for nm in ['raw','shee','parq','csv']:
            self.path[nm] = root_path / f'resources/flags/{nm}'

    def raw_to_parq(self, overwrite=False):
        for src in self.path['raw'].iterdir():
            src.replace(src.with_name(src.name.lower().replace(' ','_').replace('-','_')))
        k = 0
        for src in sorted(self.path['raw'].glob('*flags*.xlsx'), reverse=True):
            book = pd.ExcelFile(src, engine='openpyxl')
            try:
                dt = pd.to_datetime(src.stem[:10].replace('_','-'))
                sheets = {sheet:sheet for sheet in book.sheet_names if sheet.isnumeric() and int(sheet) % 100 in [1,6,8]}
            except:
                dt = pd.to_datetime(src.stem[-6:])
                sheets = {src.stem[:6]: book.sheet_names[0]}

            date = str(dt.date())
            for term_code, sheet in sheets.items():
                dst = self.path['sheet'] / f'{term_code}/flg_{term_code}_{date}.parq'
                if overwrite:
                    delete(dst)
                if not dst.is_file():
                    k = 0
                    print(dst)
                    mkdir(dst.parent)
                    df = book.parse(sheet)
                    df.insert(0, 'current_date', date)
                    write(dst, df)
                    delete(self.path['parq'] / f'flg_{term_code}.parq')
            k += 1
            if k > 9:
                break

    def combine(self, overwrite=False):
        col_drop = {
            '',
            'pidm_key',
            'street1_line1',
            'street1_line2',
            'unnamed:_0',
            'nvl((selectcasewhenp1.rcrapp1_',
            'nvl((selectcasewhenp1.rcrapp1_fed_coll_choice_1=:"sys_b_054"then:"sys_b_055"whenp1.rcrapp1_fed_coll_choice_2=:"sys_b_056"then:"s',
            'decisiondate',
        }

        col_repl = {
            'admt_code_desc': 'admt_desc',
            'admt_code_descr.':'admt_desc',
            'apdc':'apdc_code',
            'ap_decision':'apdc_desc',
            'app_decision':'apdc_desc',
            'decision_date':'apdc_date',
            'apdc_decision_date1': 'apdc_date',
            'apst':'apst_code',
            'app_status':'apst_desc',
            'ap_status_description': 'apst_desc',
            'campus name':'camp_desc',
            'campus_name':'camp_desc',
            'campus_code':'camp_code',
            'fafsa':'fafsa_app',
            'high_school':'hs_name',
            'sbgi_desc_high_school':'hs_name',
            'major_code':'majr_code',
            'major':'majr_desc',
            'majr_desc1':'majr_desc',
            'moa_hs':'mou_hs',
            'oren_sess':'orien_sess',
            'selected_for_verif':'selected_for_ver',
            'student_type':'styp_desc',
            'styp':'styp_code',
            'term_code_key':'term_code',
            'verif_complete':'ver_complete',
            'app_waiver_code':'waiver_code',
            'waiver_descriton':'waiver_desc',
            'tsi_hold_exists':'tsi_holds_exist',
            'zip1':'zip',
            'um_meningitis_hold_exists':'bacmen_hold_exists',
            'housing_hold_exists':'housing_holds',
        }

        for p in sorted(self.path['sheet'].iterdir(), reverse=True):
            term_code = p.stem
            dst = self.path['parq'] / f'flg_{term_code}.parq'
            csv = self.path['csv' ] / f'flg_{term_code}.csv'
            if overwrite:
                delete(dst)
            if not dst.is_file():
                print(dst)
                L = []
                for src in sorted(p.iterdir()):
                    df = read(src)
                    col_repl['campus'] = 'camp_desc' if 'campus_code' in df else 'camp_code'
                    L.append(df.dropna(axis=1, how='all').drop(columns=col_drop, errors='ignore').rename(columns=col_repl, errors='ignore'))
                write(dst, pd.concat(L))
                # delete(csv)
            # if not csv.is_file():
            #     print(csv)
            #     write(csv, read(dst), index=False)

    def completeness(self):
        L = []
        for parq in sorted(self.path['parq'].iterdir(), reverse=True):
            df = read(parq)
            L.append((100 * df.count() / df.shape[0]).round().rename(parq.stem[-6:]).to_frame().T.prep())
        return pd.concat(L)

    def run(self, overwrite=False):
        self.raw_to_parq(overwrite)
        self.combine(overwrite)
        # return self.completeness()

#################################### TERM ####################################

@dataclasses.dataclass
class TERM(MyBaseClass):
    term_code: int
    cycle_day: int = 0
    overwrite: typing.Dict = None
    show: typing.Dict = None

    def __post_init__(self):
        self.path = dict()
        for nm in ['dst','trm']:
            self.path[nm] = root_path / f'admitted_matriculation_predictor/src'
        for nm in ['adm','reg','flg','raw']:
            self.path[nm] = root_path /f'resources/data/{nm}/{self.term_code}'
        D = {'trm':False, 'adm':False, 'reg':False, 'flg':False, 'raw':False}
        for nm in ['overwrite','show']:
            self[nm] = D.copy() if self[nm] is None else D.copy() | self[nm]
        self.overwrite['dst'] = False

        self.year = self.term_code // 100
        # self.term = self.term_code % 100
        self.appl_term_code = [self.term_code, self.term_code-2] if self.term_code % 100 == 8 else [self.term_code]
        T = [self.get_trm().query("term_code==@t").squeeze() for t in self.appl_term_code]
        self.appl_term_desc = [t['term_desc'] for t in T]
        self.term_desc = T[0]['term_desc']
        self.census_date = T[0]['census_date']
        self.end_date = self.census_date + pd.Timedelta(days=7)
        self.cycle_date = self.end_date - pd.Timedelta(days=self.cycle_day)

        self.flg_col = {
            'perm': [
                'id',
                'current_date',
                'styp_code',
                # 'transfer_hours',
                # 'inst_hours',
                # 'overall_hours',
                # 'inst_gpa',
                # 'overall_gpa',
                'fafsa_app',
                # 'finaid_offered',
                'finaid_accepted',
                # 'finaid_declined',
                'disb_req_complete',
                'schlship_app',
                # 'declined_schlrship',
                'math',
                'reading',
                'writing',
                'gap_score',
                ],
            'temp': [
                'app_date',
                'term_code',
                'ssb_last_accessed',
                'waiver_code',
                'ftic_gap_score',
                't_gap_score',
                'orien_sess',
                'orientation_hold_exists',
                'registered',
                'ver_complete',
                'selected_for_ver',
                'act_new_comp_score',
                'sat10_total_score',
                ],
        }

    def get(self, nm, cycle_day=None):
        cd = '' if cycle_day is None else '_'+rjust(cycle_day,3,0)
        fn = self.path[nm] / f"{nm}{cd}.parq"
        df = read(fn, self.overwrite[nm])
        if df is None:
            print(f'{fn.name} not found - creating')
            # print(f'{fn} not found - creating')
        return fn, df

    def run(self, qry, fn=None, show=False, func=lambda x: x):
        df = func(db.execute(qry, show=show).prep())
        if fn is not None:
            write(fn, df, overwrite=True)
        return df

    def get_trm(self):
        nm = 'trm'
        fn, df = self.get(nm)
        if df is not None:
            return df
        qry = f"""
        select
            A.stvterm_code as term_code,
            replace(A.stvterm_desc, ' ', '') as term_desc,
            A.stvterm_start_date as start_date,
            A.stvterm_end_date as end_date,
            A.stvterm_fa_proc_yr as fa_proc_yr,
            A.stvterm_housing_start_date as housing_start_date,
            A.stvterm_housing_end_date as housing_end_date,
            B.sobptrm_census_date as census_date
        from stvterm A, sobptrm B
        where A.stvterm_code = B.sobptrm_term_code and B.sobptrm_ptrm_code='1'"""
        return self.run(qry, fn, self.show[nm])

    def get_dst(self):
        nm = 'dst'
        fn, df = self.get(nm)
        assert df is not None, f"Can't find distances file {fn.name}- you probably have the wrong path. If you absolutely must recreate it, the original code is below. But it has not been tested since originally written in December 2023. It will almost surely have bugs that will require signficant effort to correct. You should exhaust every option to find the existing distance file before trying to run it."
        if df is not None:
            return df
        # import zipcodes, openrouteservice
        # client = openrouteservice.Client(key=os.environ.get('OPENROUTESERVICE_API_KEY1'))
        # def get_distances(Z, eps=0):
        #     theta = np.random.rand(len(Z))
        #     Z = Z + eps * np.array([np.sin(theta), np.cos(theta)]).T
        #     L = []
        #     dk = 1000 // len(dst)
        #     k = 0
        #     while k < len(Z):
        #         print(f'getting distances {rjust(k,5)} / {len(Z)} = {rjust(round(k/len(Z)*100),3)}%')
        #         src = Z.iloc[k:k+dk]
        #         X = pd.concat([dst,src]).values.tolist()
        #         res = client.distance_matrix(X, units="mi", destinations=list(range(0,len(dst))), sources=list(range(len(dst),len(X))))
        #         L.append(pd.DataFrame(res['durations'], index=src.index, columns=camp.keys()))
        #         k += dk
        #     return pd.concat(L)

        # Z = [[z['zip_code'],z['state'],z['long'],z['lat']] for z in zipcodes.list_all() if z['state'] not in ['PR','AS','MH','PW','MP','FM','GU','VI','AA','HI','AK','AP','AE']]
        # Z = pd.DataFrame(Z, columns=['zip','state','lon','lat']).prep().query('lat>20').set_index(['zip','state']).sort_index()
        # camp = {'s':76402, 'm':76036, 'w':76708, 'r':77807, 'l':76065}
        # dst = Z.loc[camp.values()]
        # try:
        #     df = read(fn)
        # except:
        #     df = get_distances(Z)
        # for k in range(20):
        #     mask = df.isnull().any(axis=1)
        #     if mask.sum() == 0:
        #         break
        #     df = df.combine_first(get_distances(Z.loc[mask], 0.02*k))
        # return write(fn, df.assign(o = 0).melt(ignore_index=False, var_name='camp_code', value_name='distance').prep())
    
    # def flg_fill(self):
    #     F = dict()
    #     for fn in sorted(self.path['flg'].iterdir()):
    #         term_code = int(fn.stem[-6:])
    #         if term_code >= 202006:
    #             F[term_code] = read(fn).notnull().mean()*100
    #     return pd.DataFrame(F).round().prep()

    def get_cycle_day(self, col='A.current_date'):
        return f"{dt(self.end_date)} - trunc({col})"
    
    def cutoff(self, col='A.current_date', criteria="= 0"):
        return f'{self.get_cycle_day(col)} {criteria}'
    
    def get_reg(self, cycle_day):
        nm = 'reg'
        fn, df = self.get(nm, cycle_day)
        if df is not None:
            return df
        try:
            db.head(f'opeir.registration_{self.term_desc}')
        except:
            return pd.DataFrame(columns=['current_date','cycle_day','term_code','pidm','id','levl_code','styp_code','crn','crse','credit_hr'])

        qry = f"""
select
    {cycle_day} as cycle_day,
    A.sfrstcr_term_code as term_code,
    A.sfrstcr_pidm as pidm,
    (select C.sgbstdn_levl_code from sgbstdn C where C.sgbstdn_pidm = A.sfrstcr_pidm and C.sgbstdn_term_code_eff <= A.sfrstcr_term_code order by C.sgbstdn_term_code_eff desc fetch first 1 rows only) as levl_code,
    (select C.sgbstdn_styp_code from sgbstdn C where C.sgbstdn_pidm = A.sfrstcr_pidm and C.sgbstdn_term_code_eff <= A.sfrstcr_term_code order by C.sgbstdn_term_code_eff desc fetch first 1 rows only) as styp_code,
    lower(B.ssbsect_subj_code) || B.ssbsect_crse_numb as crse,
    sum(B.ssbsect_credit_hrs) as credit_hr
from sfrstcr A, ssbsect B
where
    A.sfrstcr_term_code = B.ssbsect_term_code
    and A.sfrstcr_crn = B.ssbsect_crn
    and A.sfrstcr_term_code = {self.term_code}
    and A.sfrstcr_ptrm_code not in ('28','R3')
    and  {self.get_cycle_day('A.sfrstcr_add_date')} >= {cycle_day}  -- added before cycle_day
    and ({self.get_cycle_day('A.sfrstcr_rsts_date')} < {cycle_day} or A.sfrstcr_rsts_code in ('DC','DL','RD','RE','RW','WD','WF')) -- dropped after cycle_day or still enrolled
    and B.ssbsect_subj_code <> 'INST'
group by A.sfrstcr_term_code, A.sfrstcr_pidm, B.ssbsect_subj_code, B.ssbsect_crse_numb"""

        qry = f"""
with A as {subqry(qry)}
select A.* from A
union all
select
    A.cycle_day, A.term_code, A.pidm, A.levl_code, A.styp_code,
    '_total' as crse,
    sum(A.credit_hr) as credit_hr
from A
group by A.cycle_day, A.term_code, A.pidm, A.levl_code, A.styp_code"""
        return self.run(qry, fn, self.show[nm])


    def get_adm(self, cycle_day):
        nm = 'adm'
        fn, df = self.get(nm, cycle_day)
        if df is not None:
            return df

        def f(term_desc):
            accept = "A.apst_code = 'D' and A.apdc_code in (select stvapdc_code from stvapdc where stvapdc_inst_acc_ind is not null)"
            reject = "(A.apst_code in ('X', 'W')) or (A.apst_code = 'D' and (substr(A.apdc_code,1,1) in ('D','W') or A.apdc_code = 'RJ'))"
            sel = join([
                f"{self.get_cycle_day()} as cycle_day",
                f"trunc(A.current_date) as cycle_date",
                f"min(trunc(A.current_date)) over (partition by A.pidm, A.appl_no) as appl_date",  # first date on snapshot table (saradap_appl_date has too many consistencies so this replaces it)
                f"min(case when {accept} then trunc(A.current_date) end) over (partition by A.pidm, A.appl_no) as apdc_date",  # first date accepted
                f"A.pidm",
                f"A.id",
                f"A.term_code as term_code_entry",
                f"A.levl_code",
                f"A.styp_code",
                f"A.admt_code",
                f"A.appl_no",
                f"A.apst_code",
                f"A.apdc_code",
                f"A.camp_code",
                f"A.saradap_resd_code as resd_code",
                f"A.coll_code_1 as coll_code",
                f"A.majr_code_1 as majr_code",
                f"A.dept_code",
                f"A.hs_percentile as hs_pctl",
            ], C+N)

            qry = f"select {indent(sel)}{N}from opeir.admissions_{term_desc} A"
            
            sel = join([
                f"A.*",
                f"case{N+T}when max(case when A.cycle_day >= {cycle_day} then A.cycle_date end) over (partition by A.pidm, A.appl_no) = A.cycle_date then 1{N+T}end as r1",  # finds most recent daily snapshot BEFORE cycle_day
                f"case{N+T}when sum(case when A.cycle_day <  {cycle_day} then 1 else 0 end) over (partition by A.pidm, A.appl_no) >= {cycle_day}/2 then 1{N+T}when sysdate - {dt(self.cycle_date)} < 5 then 1{N+T}end as r2",  # check if appears on >= 50% of daily snapshots AFTER cycle_day
            ], C+N)

            qry = f"select {indent(sel)}{N}from {subqry(qry)} A where cycle_day between 0 and {cycle_day} + 14 and {accept}"
            qry = f"select A.* from {subqry(qry)} A where A.r1 = 1 and A.r2 = 1"
            return qry
        qry = join([f(term_desc).strip() for term_desc in self.appl_term_desc], "\n\nunion all\n\n")
        
        stat_codes = join(['AL','AR','AZ','CA','CO','CT','DC','DE','FL','GA','IA','ID','IL','IN','KS','KY','LA','MA','MD','ME','MI','MN','MO','MS','MT','NC','ND','NE','NH','NJ','NM','NV','NY','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VA','VT','WA','WI','WV','WY'], "', '")
        def get_spraddr(nm):
            sel = "to_number(substr(B.spraddr_zip, 0, 5) default null on conversion error)" if nm == "zip" else "B.spraddr_"+nm
            return f"""
(select B.{nm} from (
    select
        {sel} as {nm},
        B.spraddr_seqno as s,
        case
            when B.spraddr_atyp_code = 'PA' then 6
            when B.spraddr_atyp_code = 'PR' then 5
            when B.spraddr_atyp_code = 'MA' then 4
            when B.spraddr_atyp_code = 'BU' then 3
            when B.spraddr_atyp_code = 'BI' then 2
            --when B.spraddr_atyp_code = 'P1' then 1
            --when B.spraddr_atyp_code = 'P2' then 0
            end as r
    from spraddr B where B.spraddr_pidm = A.pidm and B.spraddr_stat_code in ('{stat_codes}')
) B where B.{nm} is not null and B.r is not null
order by B.r desc, B.s desc fetch first 1 row only) as {nm}""".strip()

        sel = join([
            f"A.*",
            f"row_number() over (partition by A.pidm order by A.appl_no desc) as r",
            f"{self.term_code} as term_code",
            get_spraddr("cnty_code"),
            get_spraddr("stat_code"),
            get_spraddr("zip"),
            f"(select B.gorvisa_natn_code_issue from gorvisa B where B.gorvisa_pidm = A.pidm order by gorvisa_seq_no desc fetch first 1 row only) as natn_code",
            f"(select B.spbpers_lgcy_code from spbpers B where B.spbpers_pidm = A.pidm) as lgcy_code",
            f"(select B.spbpers_birth_date from spbpers B where B.spbpers_pidm = A.pidm) as birth_date",
        ], C+N)
        qry = f"select {indent(sel)}{N}from {subqry(qry)} A"
        
        sel = N+T+join([
            f"A.cycle_day",
            f"{self.get_cycle_day('apdc_date')} as apdc_day",
            f"{self.get_cycle_day('appl_date')} as appl_day",
            f"{self.get_cycle_day('birth_date')} as birth_day",
            f"{dt(self.end_date)} as end_date",
            f"A.cycle_date",
            f"A.apdc_date",
            f"A.appl_date",
            f"A.birth_date",
            f"A.term_code_entry",
            *get_desc('term'),
            f"A.pidm",
            f"A.id",
            f"A.appl_no",
            *get_desc('levl'),
            *get_desc('styp'),
            *get_desc('admt'),
            *get_desc('apst'),
            *get_desc('apdc'),
            *get_desc('camp'),
            # f"case when A.camp_code = 'S' then 1 end as camp_main",
            *get_desc('coll'),
            *get_desc('dept'),
            *get_desc('majr'),
            *get_desc('cnty'),
            *get_desc('stat'),
            f"A.zip",
            f"A.natn_code",
            f"(select B.stvnatn_nation from stvnatn B where B.stvnatn_code = A.natn_code) as natn_desc",
            f"coalesce((select distinct 1 from gorvisa B where B.gorvisa_pidm = A.pidm and B.gorvisa_vtyp_code is not null), 0) as international",
            f"coalesce((select distinct 1 from gorprac B where B.gorprac_pidm = A.pidm and B.gorprac_race_cde='IN'), 0) as race_american_indian",
            f"coalesce((select distinct 1 from gorprac B where B.gorprac_pidm = A.pidm and B.gorprac_race_cde='AS'), 0) as race_asian",
            f"coalesce((select distinct 1 from gorprac B where B.gorprac_pidm = A.pidm and B.gorprac_race_cde='BL'), 0) as race_black",
            f"coalesce((select distinct 1 from gorprac B where B.gorprac_pidm = A.pidm and B.gorprac_race_cde='HA'), 0) as race_pacific",
            f"coalesce((select distinct 1 from gorprac B where B.gorprac_pidm = A.pidm and B.gorprac_race_cde='WH'), 0) as race_white",
            f"coalesce((select distinct 1 from spbpers B where B.spbpers_pidm = A.pidm and B.spbpers_ethn_cde=2   ), 0) as race_hispanic",
            f"(select B.spbpers_sex from spbpers B where B.spbpers_pidm = A.pidm) as gender",
            *get_desc('lgcy'),
            *get_desc('resd'),
            f"A.hs_pctl"
        ], C+N)
        qry = f"select {indent(sel)}\nfrom {subqry(qry)} A where A.r = 1 and A.levl_code = 'UG' and A.styp_code in ('N','R','T')"
        return self.run(qry, fn, self.show[nm])


    def get_flg(self, cycle_day):
        nm = 'flg'
        fn, df = self.get(nm, cycle_day)
        if df is not None:
            return df
        F = []
        for term_code in self.appl_term_code:
            raw = FLAGS().path['parq'] / f"flg_{term_code}.parq"
            df = read(raw, columns=['current_date'])
            df['cycle_day'] = (self.end_date - df['current_date']).dt.days
            flg_day  = df.query(f'cycle_day>={cycle_day}')['cycle_day'].min()
            flg_date = df.query(f'cycle_day==@flg_day')['current_date'].min()
            filters = [('current_date','==',flg_date)]
            L = []
            missing = []
            if self.flg_col is None:
                df = read(raw, filters=filters)
            else:
                for c in sum(self.flg_col.values(),[]):
                    x = read(raw, filters=filters, columns=[c])
                    if x is None:
                        missing.append(c)
                        x = L[0][[]].assign(**{c:pd.NA})
                    L.append(x)
                df = pd.concat(L, axis=1)
            print(f'{term_code} flags cycle day {flg_day} >= {cycle_day} on {flg_date} missing columns: {missing}')
            F.append(df)
        with warnings.catch_warnings(action='ignore'):
            subset = ['id','term_code_entry','styp_code']
            df = (
                pd.concat(F, ignore_index=True)
                .prep()
                .rename(columns={'current_date':'flg_date', 'term_code':'term_code_entry'})
                .sort_values(by=[*subset,'app_date'])
                .drop_duplicates(subset=subset, keep='last')
                .copy()
            )
        df['gap_score'] = np.where(df['styp_code']=='n', df['ftic_gap_score'].combine_first(df['t_gap_score']).combine_first(df['gap_score']), df['t_gap_score'].combine_first(df['ftic_gap_score']).combine_first(df['gap_score']))
        df['ssb'] = df['ssb_last_accessed'].notnull()
        df['waiver'] = df['waiver_code'].notnull()
        df['oriented'] = np.where(df['orien_sess'].notnull() | df['registered'].notnull(), 'y', np.where(df['orientation_hold_exists'].notnull(), 'n', 'w'))
        df['verified'] = np.where(df['ver_complete'].notnull(), 'y', np.where(df['selected_for_ver'].notnull(), 'n', 'w'))
        df['sat10_total_score'] = (36-9) / (1600-590) * (df['sat10_total_score']-590) + 9
        df['act_equiv'] = df[['act_new_comp_score','sat10_total_score']].max(axis=1)
        for k in ['reading', 'writing', 'math']:
            df[k] = ~df[k].isin(['not college ready', 'retest required', pd.NA])
        return write(fn, df.drop(columns=self.flg_col['temp']+['cycle_day'], errors='ignore').dropna(axis=1, how='all'))


    def get_raw(self):
        self['reg'] = {k: self.get_reg(cycle_day) for k, cycle_day in {'end':0, 'cur':self.cycle_day}.items()}
        
        nm = 'raw'
        fn, df = self.get(nm, self.cycle_day)
        if df is None:
            self.adm = self.get_adm(self.cycle_day)
            self.adm.loc[self.adm.eval('pidm==1121725'), 'zip'] = 76109  # ad hoc fix to data error which I've requested to be fixed
            self.flg = self.get_flg(self.cycle_day)
            self.dst = self.get_dst()
            df =  (
                self.adm
                .merge(self.flg, how='left', on=['id','term_code_entry','styp_code'])
                .merge(self.dst, how='left', on=['zip','camp_code'])
                .prep()
            )
            assert (df.groupby(['pidm','term_code']).size() == 1).all()
            write(fn, df)
        self[nm] = df
        return self
    
###############################################################################

# from LiveAMP import *
import miceforest as mf
from sklearn.compose import make_column_selector, ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, PowerTransformer, KBinsDiscretizer
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.metrics import f1_score
from sklearn import set_config
set_config(transform_output="pandas")

def feature_importance_df(self, dataset=0, iteration=None, normalize=True):
    targ = [self._get_var_name_from_scalar(int(i)) for i in np.sort(self.imputation_order)]
    feat = [self._get_var_name_from_scalar(int(i)) for i in np.sort(self.predictor_vars)]
    I = pd.DataFrame(self.get_feature_importance(dataset, iteration), index=targ, columns=feat).T
    return I / I.sum() * 100 if normalize else I
mf.ImputationKernel.feature_importance_df = feature_importance_df

def inspect(self, **kwargs):
    self.plot_imputed_distributions(wspace=0.3,hspace=0.3)
    plt.show()
    self.plot_mean_convergence(wspace=0.3, hspace=0.4)
    plt.show()
    I = self.feature_importance_df(**kwargs)
    I.disp(100)
    return I
mf.ImputationKernel.inspect = inspect


@dataclasses.dataclass
class AMP(MyBaseClass):
    cycle_day: int
    term_codes: typing.List
    infer_term: int
    crse: typing.List
    attr: typing.List
    fill: typing.Dict = None
    trf_grid: typing.Dict = None
    imp_grid: typing.Dict = None
    overwrite: typing.Dict = None
    show: typing.Dict = None
    inspect: bool = False

    def dump(self):
        return write(self.rslt, self, overwrite=True)

    def __post_init__(self):
        self.rslt = root_path / f"resources/rslt/{rjust(self.cycle_day,3,0)}/rslt.pkl"
        D = {'trm':False, 'adm':False, 'reg':False, 'flg':False, 'raw':False, 'term':False, 'raw_df':False, 'reg_df':False, 'X':False, 'Y':False, 'pred':False}
        for x in ['overwrite','show']:
            self[x] = D.copy() if self[x] is None else D.copy() | self[x]
        self.overwrite['reg_df'] = True

        self.overwrite['raw'] |= self.overwrite['reg'] | self.overwrite['adm'] | self.overwrite['flg']
        self.overwrite['term'] |= self.overwrite['raw']
        self.overwrite['raw_df'] |= self.overwrite['term']
        self.overwrite['reg_df'] |= self.overwrite['term']
        self.overwrite['X'] |= self.overwrite['raw_df']
        self.overwrite['Y'] |= self.overwrite['reg_df'] | self.overwrite['X']

        try:
            self.__dict__ = read(self.rslt).__dict__ | self.__dict__
        except:
            pass

        for k, v in self.overwrite.items():
            if v and k in self:
                del self[k]
        for k in ['fill','term','pred','trf_grid','imp_grid']:
            if k not in self:
                print(k)
                self[k] = dict()

        self.term_codes = uniquify([*listify(self.term_codes), self.infer_term])
        self.crse = uniquify(['_total', *listify(self.crse)])
        self.mlt_grp = ['crse','levl_code','styp_code','term_code']
        self.trf_list = cartesian({k: sorted(setify(v), key=str) for k,v in self.trf_grid.items()})
        self.trf_list = [mysort({k:v for k,v in t.items() if v not in ['drop',None,'']}) for t in self.trf_list]
        imp_default = {'iterations':3, 'mmc':0, 'mmf':'mean_match_default', 'datasets':5, 'tune':True}
        self.imp_list = cartesian(self.imp_grid)
        self.imp_list = [mysort(imp_default | v) for v in self.imp_list]
        self.params_list = sorted([mysort({'imp':imp, 'trf':trf}) for trf, imp in it.product(self.trf_list,self.imp_list)], key=str)
        return self


    def get_terms(self):
        opts = {x:self[x] for x in ['cycle_day','overwrite','show']}
        for nm in self.term_codes:
            if nm not in self.term:
                print(f'get {nm}')
                self.term[nm] = TERM(term_code=nm, **opts).get_raw()


    def preprocess(self):
        def get(nm):
            if nm in self:
                return False
            print(f'get {nm}')
            return True

        if get('raw_df') or get('reg_df'):
            self.get_terms()

        if get('raw_df'):
            with warnings.catch_warnings(action='ignore'):
                self.raw_df = pd.concat([term.raw for term in self.term.values()], ignore_index=True).dropna(axis=1, how='all').prep()

        if get('reg_df'):
            with warnings.catch_warnings(action='ignore'):
                self.reg_df = {k: pd.concat([term.reg[k].query("crse in @self.crse") for term in self.term.values()]).prep() for k in ['cur','end']}

        where = lambda x: x.query("levl_code == 'ug' and styp_code in ('n','r','t')").copy()
        if get('X'):
            R = self.raw_df.copy()
            repl = {'ae':0, 'n1':1, 'n2':2, 'n3':3, 'n4':4, 'r1':1, 'r2':2, 'r3':3, 'r4':4}
            R['hs_qrtl'] = pd.cut(R['hs_pctl'], bins=[-1,25,50,75,90,101], labels=[4,3,2,1,0], right=False).combine_first(R['apdc_code'].map(repl))
            R['remote'] = R['camp_code'] != 's'
            R['resd'] = R['resd_code'] == 'r'
            R['lgcy'] = ~R['lgcy_code'].isin(['n','o'])
            R['majr_code'] = R['majr_code'].replace({'0000':'und', 'eled':'eted', 'agri':'unda'})
            R['coll_code'] = R['coll_code'].replace({'ae':'an', 'eh':'ed', 'hs':'hl', 'st':'sm', '00':pd.NA})
            R['coll_desc'] = R['coll_desc'].replace({
                'ag & environmental_sciences':'ag & natural_resources',
                'education & human development':'education',
                'health science & human_service':'health sciences',
                'science & technology':'science & mathematics'})
            majr = ['majr_desc','dept_code','dept_desc','coll_code','coll_desc']
            S = R.sort_values('cycle_date').drop_duplicates(subset='majr_code', keep='last')[['majr_code',*majr]]
            X = where(R.drop(columns=majr).merge(S, on='majr_code', how='left')).prep().prep_bool()

            checks = [
                'cycle_day >= 0',
                'apdc_day >= cycle_day',
                'appl_day >= apdc_day',
                'birth_day >= appl_day',
                'birth_day >= 5000',
                'distance >= 0',
                'hs_pctl >=0',
                'hs_pctl <= 100',
                'hs_qrtl >= 0',
                'hs_qrtl <= 4',
                'act_equiv >= 1',
                'act_equiv <= 36',
                'gap_score >= 0',
                'gap_score <= 100',
            ]
            for check in checks:
                mask = X.eval(check)
                assert mask.all(), [check,X[~mask].disp(5)]
            
            for k, v in self.fill.items():
                X[k] = X.impute(k, *listify(v))
            self.X = X.prep().prep_bool().set_index(self.attr, drop=False).rename(columns=lambda x:'__'+x)
            self.X.missing().disp(100)

        if get('Y'):
            Y = {k: self.X[[]].join(y.set_index(['pidm','term_code','crse'])['credit_hr']) for k, y in self.reg_df.items()}
            agg = lambda y: where(y).groupby(self.mlt_grp)['credit_hr'].agg(lambda x: (x>0).sum())
            A = agg(self.reg_df['end'])
            B = agg(Y['end'])
            M = (A / B).replace(np.inf, pd.NA).rename('mlt').reset_index().query(f"term_code != {self.infer_term}").prep()
            N = M.assign(term_code=self.infer_term)
            self.mlt = pd.concat([M, N], axis=0).set_index(self.mlt_grp)
            Y = {k: y.squeeze().unstack().dropna(how='all', axis=1).fillna(0) for k, y in Y.items()}
            self.Y = Y['cur'].rename(columns=lambda x:x+'_cur').join(Y['end']>0).prep()
        self.dump()


    def predict(self, params, crse, train_term, styp_code='all'):
        print(ljust(crse,8), train_term, styp_code, 'creating')
        X = self.X.copy()
        if styp_code != 'all':
            X = X.query(f"styp_code==@styp_code")
        trf = ColumnTransformer([(c,t,["__"+c]) for c,t in params['trf'].items()], remainder='drop', verbose_feature_names_out=False)
        cols = uniquify(['_total_cur',crse+'_cur',crse])
        Z = trf.fit_transform(X).join(self.Y[cols]).prep().prep_bool().prep_category().sort_index()
        y = Z[crse].copy().rename('true').to_frame()
        Z.loc[Z.eval("term_code!=@train_term"), crse] = pd.NA

        iterations = params['imp'].pop('iterations')
        datasets = params['imp'].pop('datasets')
        tune = params['imp'].pop('tune')
        mmc = params['imp'].pop('mmc')
        mmf = params['imp'].pop('mmf')
        if mmc > 0 and mmf is not None:
            params['imp']['mean_match_scheme'] = getattr(mf, mmf).copy()
            params['imp']['mean_match_scheme'].set_mean_match_candidates(mmc)
        
        if tune:
            # print('tuning')
            imp = mf.ImputationKernel(Z, datasets=1, **params['imp'])
            imp.mice(iterations=1)
            optimal_parameters, losses = imp.tune_parameters(dataset=0, optimization_steps=5)
        else:
            # print('not tuning')
            optimal_parameters = None
        imp = mf.ImputationKernel(Z, datasets=datasets, **params['imp'])
        imp.mice(iterations=iterations, variable_parameters=optimal_parameters)
        if self.inspect:
            imp.inspect()

        Z.loc[:, crse] = pd.NA
        P = imp.impute_new_data(Z)
        details = pd.concat([y
                .assign(pred=P.complete_data(k)[crse], train_term=train_term, crse=crse, sim=k)
                .set_index(['train_term','crse','sim'], append=True)
            for k in range(P.dataset_count())]).prep_bool()
        agg = lambda x: pd.Series({
            'pred': x['pred'].sum(min_count=1),
            'true': x['true'].sum(min_count=1),
            'mse_pct': ((1*x['pred'] - x['true'])**2).mean()*100,
            'f1_inv_pct': (1-f1_score(x.dropna()['true'], x.dropna()['pred'], zero_division=np.nan))*100,
        })
        summary = details.groupby([*self.mlt_grp,'train_term','sim']).apply(agg).join(self.mlt).rename_axis(index={'term_code':'pred_term'})
        for x in ['pred','true']:
            summary[x] = summary[x] * summary['mlt']
        summary.insert(2, 'err', summary['pred'] - summary['true'])
        summary.insert(3, 'err_pct', (summary['err'] / summary['true']).clip(-1, 1) * 100)
        S = {'details':details, 'summary':summary.drop(columns='mlt').prep()}#, 'trf':trf, 'imp':imp}
        # S['summary'].disp(5)
        return S
        # return S, True


    def analyze(self, df):
        def pivot(df, val):
            Y = (
                df
                .reset_index()
                .pivot_table(columns='train_term', index=['crse','styp_code','pred_term'], values=val, aggfunc=['count',pctl(0),pctl(25),pctl(50),pctl(75),pctl(100)])
                .rename_axis(columns=[val,'train_term'])
                .stack(0, future_stack=True)
                .assign(abs_mean = lambda x: x.abs().mean(axis=1))
            )
            return Y
        mask = df.eval(f"pred_term!={self.infer_term}")
        return {stat: pivot(df[mask], stat) for stat in ["pred","err","err_pct","mse_pct","f1_inv_pct"]} | {"proj": pivot(df[~mask], "pred")}

    def main(self, styp_codes=('n','t','r')):
        self.preprocess()
        g = lambda Y: {k: pd.concat([y[k] for y in Y.values() if isinstance(y, dict) and k in y.keys()]).sort_index() for k in ['details','summary']}
        start_time = time.perf_counter()
        L = len(self.params_list)
        k = 0
        for params in self.params_list:
            print(str(params))
            new = False
            Y = []
            for crse in self.crse:
                for train_term in self.term_codes:
                    for styp_code in listify(styp_codes):
                        path = [str(params),crse,train_term,styp_code]
                        try:
                            y = nest(path, self.pred)
                        except:
                            if not new:
                                print(str(params))
                            y = self.predict(copy.deepcopy(params), crse, train_term, styp_code)
                            nest(path, self.pred, y)
                            new = True
                            self.dump()
                        Y.append(y)
            P = self.pred[str(params)]
            if new:
                for key in ['details', 'summary']:
                    P[key] = pd.concat([y[key] for y in Y])
                P['rslt'] = self.analyze(P['summary'])
                self.dump()
                k += 1
            else:
                L -= 1
            P['rslt']['err_pct'].query("err_pct == ' 50%'").disp(100)
            P['summary'].query(f"train_term==202308 & pred_term!=202408")["err_pct"].abs().describe().to_frame().T.disp(200)
            elapsed = (time.perf_counter() - start_time) / 60
            complete = k / L if L > 0 else 1
            rate = elapsed / k if k > 0 else 0
            remaining = rate * (L - k)
            print(f"{k} / {L} = {round(complete*100,1)}% complete, elapsed = {round(elapsed,1)} min, remaining = {round(remaining,1)} min @ {round(rate,1)} min per model")
            print("\n========================================================================================================\n")
    

if __name__ == "__main__":
    code_desc = lambda x: [x+'_code', x+'_desc']
    passthru = ['passthrough']
    passdrop = ['passthrough', 'drop']
    # passthru = passdrop
    bintrf = lambda n_bins: KBinsDiscretizer(n_bins=n_bins, encode='ordinal', strategy='uniform', subsample=None)
    pwrtrf = make_pipeline(StandardScaler(), PowerTransformer())
    kwargs = {
        # 'term_codes': np.arange(2020,2025)*100+8,
        'term_codes': np.arange(2021,2025)*100+8,
        'infer_term': 202408,
        'show': {
            # 'reg':True,
            # 'adm':True,
        },
        'fill': {
            'birth_day': ['median',['term_code','styp_code']],
            'remote': False,
            'international': False,
            **{f'race_{r}': False for r in ['american_indian','asian','black','pacific','white','hispanic']},
            'lgcy': False,
            'resd': False,
            'waiver': False,
            'fafsa_app': False,
            'schlship_app': False,
            'finaid_accepted': False,
            'ssb': False,
            'math': False,
            'reading': False,
            'writing': False,
            'gap_score': 0,
            'oriented': 'n',
        },
        'attr': [
            'pidm',
            *code_desc('term'),
            *code_desc('apdc'),
            *code_desc('levl'),
            *code_desc('styp'),
            *code_desc('admt'),
            *code_desc('camp'),
            *code_desc('coll'),
            *code_desc('dept'),
            *code_desc('majr'),
            *code_desc('cnty'),
            *code_desc('stat'),
            *code_desc('natn'),
            *code_desc('resd'),
            *code_desc('lgcy'),
            'international',
            'gender',
            *[f'race_{r}' for r in ['american_indian','asian','black','pacific','white','hispanic']],
            'waiver',
            'birth_day',
            'distance',
            'hs_qrtl',
        ],
        'cycle_day': (TERM(term_code=202408).cycle_date-pd.Timestamp.now()).days+1,
        'cycle_day': 183,
        'crse': [
            'engl1301',
            'biol1406',
            # 'math1314',
            # 'biol2401',
            # 'math2412',
            # 'agri1419',
            # 'psyc2301',
            # 'ansc1319',
            # 'comm1311',
            # 'hist1301',
            # 'govt2306',
            # 'math1324',
            # 'chem1411',
            # 'univ0301',
            # 'univ0204',
            # 'univ0304',
            # 'agri1100',
            # 'comm1315',
            # 'agec2317',
            # 'govt2305',
            # 'busi1301',
            # 'arts1301',
            # 'math1342',
            # 'math2413',
            ],
        'trf_grid': {
            'act_equiv': passthru,
            # 'admt_code': passdrop,
            'apdc_day': passthru,
            # 'appl_day': passthru,
            'birth_day': [*passthru, pwrtrf],#, ],
            # 'camp_code': passdrop,
            'coll_code': passthru,
            'distance': [*passthru, pwrtrf],#, bintrf(5)],
            # 'fafsa_app': passthru,
            # 'finaid_accepted': passthru,
            'gap_score': passthru,
            'gender': passthru,
            'hs_qrtl': passthru,
            'international': passthru,
            # 'levl_code': passthru,
            'lgcy': passthru,
            'math': passthru,
            'oriented': passthru,
            **{f'race_{r}': passthru for r in ['american_indian','asian','black','pacific','white','hispanic']},
            'reading': passthru,
            'remote': passthru,
            'resd': passthru,
            'schlship_app': passthru,
            'ssb': passthru,
            # 'styp_code': passthru,
            'waiver': passdrop,
            'writing': passthru,
            },
        'imp_grid': {
            'mmc': 10,
            # 'datasets': 25,
            # 'datasets': 1,
            # 'iterations': 1,
            # 'tune': False,
        },
        'overwrite': {
            # # 'trm':True,
            # 'reg':True,
            # 'adm':True,
            # 'flg':True,
            # 'raw':True,
            # 'term': True,
            # 'raw_df': True,
            # 'reg_df': True,
            # 'X': True,
            # 'Y': True,
            # 'pred': True,
        },
        # 'inspect': True,
    }

    from IPython.utils.io import Tee
    from contextlib import closing
    
    # FLAGS().run()
    self = AMP(**kwargs)
    
    with closing(Tee(self.rslt.with_suffix('.txt'), "w", channel="stdout")) as outputstream:
        print(pd.Timestamp.now())
        self.preprocess()
        self.term_codes.remove(self.infer_term)
        # self.params_list = self.params_list[102:103]
        self.main(styp_codes='n')
        # print(len(self.params_list))
        # for x in self.params_list:
        #     print(x)
        # T = TERM(202008, cycle_day=184, show={'adm':True}).get_adm(184)