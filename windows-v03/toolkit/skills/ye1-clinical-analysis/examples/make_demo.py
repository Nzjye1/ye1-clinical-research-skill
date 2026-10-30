"""Create an invented cohort in a fresh project; never use this for clinical input."""
from pathlib import Path
import argparse,csv,json,math,random
p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);p.add_argument("--seed",type=int,default=20261107);p.add_argument("--rows",type=int,default=640);a=p.parse_args()
if not 100<=a.rows<=1000:p.error("rows must be between 100 and 1000")
root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False);(root/"runs").mkdir()
rng=random.Random(a.seed);rows=[]
for i in range(a.rows):
    age=round(rng.gauss(61,10),2);exposure=round(rng.gauss(3.5,1.2),3);arm="A" if i%3==0 else "B"
    eta=-1.1+.3*(exposure-4)+.018*(age-58)+.2*(arm=="B")
    outcome=str(int(rng.random()<1/(1+math.exp(-eta))))
    true=rng.expovariate(.018*math.exp(.20*(exposure-3.5)+.009*(age-61)+.12*(arm=="B")))
    censor=rng.uniform(24,60);follow=round(min(true,censor),5);event="1" if true<=censor else "0"
    rows.append({"subject":f"INVENTED-{i:04d}","age":age if i%53 else "","exposure":exposure if i%61 else "","arm":arm,"outcome":outcome,"follow_days":max(follow,.00001),"event":event})
with (root/"synthetic.csv").open("w",encoding="utf-8",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(root/"DICTIONARY.md").write_text('''# 合成测试字典
本表完全由程序生成虚构受试者，一人一行，无权重；不是患者资料。种子与人数见 ORIGIN.json。
subject：虚构唯一键。age：基线年龄，年，少量缺失。exposure：基线连续暴露，任意单位，少量缺失。arm：A/B 基线类别，参考 A。
outcome：横断面虚构二分类结局，1=事件、0=非事件，不能解释为预测。
follow_days：从虚构入组时点至终点或末次观察的天数，>0；event：1=唯一目标事件、0=右删失。观察终点 60 天。
无竞争事件、重复事件、延迟进入或时间变化协变量；age/exposure/arm 在入组时可用。
生存例子的预定评价时点为 0/7/14/28/42 天。回归缺失策略为完整案例；描述比例以 nonmissing 为分母。
数据只用于软件验收，不形成临床假说或结论。
''',encoding="utf-8")
(root/"ORIGIN.json").write_text(json.dumps({"data_origin":"synthetic","task_purpose":"engineering_test","rows":a.rows,"seed":a.seed}),encoding="utf-8")
print(json.dumps({"status":"SYNTHETIC_PROJECT_CREATED","rows":a.rows,"seed":a.seed}))
