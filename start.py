import pandas as pd
from flask import Flask, render_template, request, jsonify
import os
import re
from datetime import datetime

app = Flask(__name__)


df = pd.DataFrame()
file_count = 0


@app.route("/")
def index():
    global file_count
    global df
    file_count = 0
    df = pd.DataFrame()
    return render_template("index2.html")


@app.route("/", methods=["POST"])
def process_data():
    global file_count
    global df
    file = request.files["netlist_file"]

    bom_file = request.files["Bom_file"]

    if file and not bom_file:
        filename = file.filename
        testfile = file.read()
        try:
            testfile = testfile.decode("cp949")
        except UnicodeDecodeError:
            try:
                testfile = testfile.decode("utf-8")
            except UnicodeDecodeError:
                testfile = testfile.decode("cp494")

        lines = testfile.splitlines()

        # 추출할 인스턴스 객체
        instance_name = request.form.get("instance_name").upper()

        data = []

        # 네트리스트 파일 처리 로직
        GND = 0
        Fv = 0
        TwV = 0
        GM = 0
        GM_SIX = 0
        FT_V = 0
        USB_V = 0
        test = 1
        Excname = ""
        Excport = ""
        for line in lines:
            item = line.split(" ")
            item = [i for i in item if i not in ""]

            if "(instance" in item:
                name = item[item.index("(instance") + 1]
                name = name.replace("\n", "")
                texts = testfile

                Val = texts.find(name)
                Val2 = texts[Val + 1 :].find("(instance")
                description = texts[Val + 1 : Val + Val2]

                if texts[Val:].find("Value (string ") != -1:
                    numtext = texts[Val:].find("Value (string ") + Val + 14
                    numtext2 = numtext + texts[numtext:].find(")")
                    value = texts[numtext:numtext2]
                else:
                    value = " "

                if description.find("Description (string") != -1:
                    Des1 = description.index("Description (string") + 19
                    Des2 = description[Des1:].index(")") + Des1
                    description = description[Des1:Des2]
                else:
                    description = " "

            if "(portInstance" in item:
                test = 0
                port = item[item.index("(portInstance") + 1]
                port = port[0 : port.find(")")]

                # 객체와 그 객체가 가지고 있는 핀(port)를 바탕으로 탐색 문장 추출
                TextPoint = "(portRef " + port + " (instanceRef " + name + "))"
                TextPoint = TextPoint.replace("\n", "")

                text = testfile

                try:
                    a = text.index(TextPoint)
                except ValueError:
                    a = -1

                if a == -1:
                    continue

                else:
                    Find_index = text[0:a]
                    NetFind = Find_index.rfind("(net ")

                    NetFind1 = NetFind + 5
                    NetFind2 = Find_index[NetFind1:].index("\n") + NetFind1

                    # 각 핀을 포함하고 있는 네트리스트 이름 추출
                    NetName = text[NetFind1:NetFind2]

                    if NetName.strip() == "GND":
                        GND = 1
                        Excname = name
                        Excport = port
                    elif NetName.strip() == "&5V":
                        Fv = 1
                        Excname = name
                        Excport = port
                    elif NetName.strip() == "FT5V":
                        FT_V = 1
                        Excname = name
                        Excport = port
                    elif NetName.strip() == "P12V":
                        TwV = 1
                        Excname = name
                        Excport = port
                    elif NetName.strip() == "+12V_GM":
                        GM = 1
                        Excname = name
                        Excport = port
                    elif NetName.strip() == "+6V_PV":
                        GM_SIX = 1
                        Excname = name
                        Excport = port
                    elif NetName.strip() == "USB5V":
                        USB_V = 1
                        Excname = name
                        Excport = port

                    else:
                        # 문장을 포함하는 네트리스트 전체 추출
                        try:
                            Find_Next = text[NetFind + 1 :].index("(net")
                        except ValueError:
                            Find_Next = -1
                        All_Net = text[NetFind : Find_Next + NetFind]

                        # 추출한 네트리스트에서 연결된 모든 객체 추출
                        connected_objects = []

                        for text in re.finditer("instanceRef ", All_Net):
                            InstanceFind1 = text.start() + 12
                            InstanceFind2 = (
                                All_Net[InstanceFind1:].index(")") + InstanceFind1
                            )
                            Find_All = All_Net[InstanceFind1:InstanceFind2]
                            if name == Find_All:
                                continue
                            connected_objects.append(Find_All)  # 연결된 객체를 리스트에 추가

                        data.append(
                            [
                                name,
                                port,
                                NetName,
                                ", ".join(connected_objects),  # 리스트를 문자열로 변환하여 추가
                                value,
                                description,
                            ]
                        )

                    if GND == 1:
                        data.append([Excname, Excport, "GND", "", value, description])
                        GND = 0
                    elif Fv == 1:
                        data.append([Excname, Excport, "5V", "", value, description])
                        Fv = 0
                    elif TwV == 1:
                        data.append([Excname, Excport, "P12V", "", value, description])
                        TwV = 0
                    elif GM == 1:
                        data.append(
                            [Excname, Excport, "+12V_GM", "", value, description]
                        )
                        GM = 0
                    elif GM_SIX == 1:
                        data.append(
                            [Excname, Excport, "+6V_PV", "", value, description]
                        )
                        GM_SIX = 0
                    elif FT_V == 1:
                        data.append([Excname, Excport, "FT5V", ""])
                        FT_V = 0
                    elif USB_V == 1:
                        data.append([Excname, Excport, "USB5V", ""])
                        USB_V = 0

                    df = pd.DataFrame(
                        data,
                        columns=[
                            "InstanName",
                            "PinName",
                            "NetName",
                            "Connect Object",
                            "value_NET",
                            "description_NET",
                        ],
                    )

        file_count += 1  # 파일 카운트 증가
        result_filename = f"ICpin{file_count}.xlsx"
        result_filepath = os.path.join(app.root_path, "static", result_filename)
        ins = instance_name

        if df.empty:
            lines = testfile.splitlines()
            data = []
            for line in lines:
                item = line.split(" ")

                if "(net" in item:
                    name = item[item.index("(net") + 1]

                if "(portRef" in item:
                    port = item[item.index("(portRef") + 1]
                if "(instanceRef" in item:
                    instan = item[item.index("(instanceRef") + 1].replace(")", "")

                    V = testfile.find(instan)
                    V2 = testfile[V + 1 :].find("(instance")
                    des = testfile[V + 1 : V + V2]

                    if testfile[V:].find("Value (string ") != -1:
                        numtext = testfile[V:].find("Value (string ") + V + 14
                        numtext2 = numtext + testfile[numtext:].find(")")
                        val = testfile[numtext:numtext2]

                    else:
                        val = ""

                    if des.find("Description (string") != -1:
                        Des1 = des.index("Description (string") + 19
                        Des2 = des[Des1:].index(")") + Des1
                        des = des[Des1:Des2]
                    else:
                        des = ""

                    instan_data = []
                    for line in lines:
                        item = line.split(" ")
                        if "(net" in item:
                            name2 = item[item.index("(net") + 1]
                        if "(portRef" in item:
                            port2 = item[item.index("(portRef") + 1]
                        if "(instanceRef" in item:
                            instan2 = item[item.index("(instanceRef") + 1].replace(
                                ")", ""
                            )

                            if name == name2 and instan2 != instan:
                                if name == name2 and instan2 != instan:
                                    if name2.strip() == "GND":
                                        continue
                                    if name2.strip() == "&5V":
                                        continue
                                    if name2.strip() == "FT5V":
                                        continue
                                    if name2.strip() == "P12V":
                                        continue
                                    if name2.strip() == "+12V_GM":
                                        continue
                                    if name2.strip() == "+6V_PV":
                                        continue
                                    if name2.strip() == "USB5V":
                                        continue
                                    instan_data.append(instan2)

                                else:
                                    instan_data.append(instan2)

                    data.append(
                        [instan, port, name, ", ".join(instan_data), val, des]
                    )  # Connect Object 추가

            df = pd.DataFrame(
                data,
                columns=[
                    "InstanName",
                    "PinName",
                    "NetName",
                    "Connect Object",
                    "value_NET",
                    "description_NET",
                ],
            )
            df["NetName"] = df["NetName"].str.replace("\n", "")
            df["InstanName"] = df["InstanName"].str.replace("\n", "")

            df = df.sort_values(by="InstanName")

            # 추출할 인스턴스 객체
            instance_name = request.form.get("instance_name").upper()
            if instance_name:
                df = df[df["InstanName"].str.upper() == instance_name]

            file_count += 1  # 파일 카운트 증가
            result_filename = f"ICpin{file_count}.xlsx"
            result_filepath = os.path.join(app.root_path, "static", result_filename)

            # 엑셀 형식 변경
            grouped_data = df.groupby(
                [
                    "InstanName",
                    "value_NET",
                    "description_NET",
                ]
            )

            # 결과 데이터 생성
            result_data = pd.DataFrame(
                columns=[
                    "InstanName",
                    "value_NET",
                    "description_NET",
                    "PinName",
                    "NetName",
                    "Connect Object",
                ]
            )
            for group, data in grouped_data:
                header_row = pd.DataFrame(
                    [group],
                    columns=[
                        "InstanName",
                        "value_NET",
                        "description_NET",
                    ],
                )
                data_columns = ["PinName", "NetName", "Connect Object"]
                data = data[data_columns]
                data = data.sort_values("PinName")  # PinPort 기준으로 정렬
                result_data = pd.concat([result_data, header_row, data])

            # 결과 엑셀 파일 생성
            result_data.to_excel(result_filepath, index=False)

            # 다운로드 링크 생성
            download_link = f"/static/{result_filename}"

            return jsonify({"result": "success", "download_link": download_link})
        else:
            if not ins and not df.empty:  # 입력이 제공되지 않고 df가 비어있지 않은 경우
                filtered_data = df  # 모든 데이터 추출
            else:
                filtered_data = pd.DataFrame()  # 빈 데이터 프레임 생성

            if not df.empty:
                if not ins:  # 입력이 제공되지 않은 경우
                    filtered_data = df  # 모든 데이터 추출
                else:  # 입력이 제공된 경우
                    filtered_data = df[df["InstanName"] == ins]

            # 엑셀 형식 변경
            grouped_data = filtered_data.groupby(
                ["InstanName", "value_NET", "description_NET"]
            )

            # 결과 데이터 생성
            result_data = pd.DataFrame(
                columns=[
                    "InstanName",
                    "value_NET",
                    "description_NET",
                    "PinName",
                    "NetName",
                    "Connect Object",
                ]
            )
            for group, data in grouped_data:
                header_row = pd.DataFrame(
                    [group], columns=["InstanName", "value_NET", "description_NET"]
                )
                data_columns = ["PinName", "NetName", "Connect Object"]
                data = data[data_columns]
                data = data.sort_values("PinName")  # PinPort 기준으로 정렬
                result_data = pd.concat([result_data, header_row, data])

            # 결과 엑셀 파일 생성
            result_data.to_excel(result_filepath, index=False)

            # 다운로드 링크 생성
            download_link = f"/static/{result_filename}"

            return jsonify({"result": "success", "download_link": download_link})

    if file and bom_file:
        print("성공")
        df = pd.read_excel(bom_file)
        seventh_column = df.iloc[:, 6]
        third_column = df.iloc[:, 2]
        sixth_column = df.iloc[:, 5]

        result = []
        for item, third, sixth in zip(seventh_column, third_column, sixth_column):
            values = str(item).split(",")
            values = [x.strip() for x in values]

            if not pd.isna(item):
                for value in values:
                    temp_values = [value, str(third), str(sixth)]
                    result.append(temp_values)

        # Netlist 파일 처리
        file = request.files["netlist_file"]
        if file:
            testfile = file.read()
            try:
                testfile = testfile.decode("cp949")
            except UnicodeDecodeError:
                try:
                    testfile = testfile.decode("utf-8")
                except UnicodeDecodeError:
                    testfile = testfile.decode("cp494")

            lines = testfile.splitlines()

            data = []
            for line in lines:
                item = line.split(" ")
                if "(net" in item:
                    name = item[item.index("(net") + 1]
                if "(portRef" in item:
                    port = item[item.index("(portRef") + 1]
                if "(instanceRef" in item:
                    instan = item[item.index("(instanceRef") + 1].replace(")", "")

                    V = testfile.find(instan)
                    V2 = testfile[V + 1 :].find("(instance")
                    des = testfile[V + 1 : V + V2]

                    if testfile[V:].find("Value (string ") != -1:
                        numtext = testfile[V:].find("Value (string ") + V + 14
                        numtext2 = numtext + testfile[numtext:].find(")")
                        val = testfile[numtext:numtext2]

                    else:
                        val = ""

                    if des.find("Description (string") != -1:
                        Des1 = des.index("Description (string") + 19
                        Des2 = des[Des1:].index(")") + Des1
                        des = des[Des1:Des2]
                    else:
                        des = ""

                    instan_data = []
                    for line in lines:
                        item = line.split(" ")
                        if "(net" in item:
                            name2 = item[item.index("(net") + 1]
                        if "(portRef" in item:
                            port2 = item[item.index("(portRef") + 1]
                        if "(instanceRef" in item:
                            instan2 = item[item.index("(instanceRef") + 1].replace(
                                ")", ""
                            )

                            if name == name2 and instan2 != instan:
                                if name == name2 and instan2 != instan:
                                    if name2.strip() == "GND":
                                        continue
                                    if name2.strip() == "&5V":
                                        continue
                                    if name2.strip() == "FT5V":
                                        continue
                                    if name2.strip() == "P12V":
                                        continue
                                    if name2.strip() == "+12V_GM":
                                        continue
                                    if name2.strip() == "+6V_PV":
                                        continue
                                    if name2.strip() == "USB5V":
                                        continue
                                    instan_data.append(instan2)

                                else:
                                    instan_data.append(instan2)

                    data.append(
                        [instan, port, name, ", ".join(instan_data), val, des]
                    )  # Connect Object 추가

            df = pd.DataFrame(
                data,
                columns=[
                    "InstanName",
                    "PinName",
                    "NetName",
                    "Connect Object",
                    "value_NET",
                    "description_NET",
                ],
            )
            df["NetName"] = df["NetName"].str.replace("\n", "")
            df["InstanName"] = df["InstanName"].str.replace("\n", "")

            df = df.sort_values(by="InstanName")

            # 'Value' 열과 'Des' 열 추가하고 값 할당
            df["value_BOM"] = ""
            df["description_BOM"] = ""

            for i, row in df.iterrows():
                instan_name = row["InstanName"]
                for item in result:
                    if instan_name == item[0]:
                        df.at[i, "value_BOM"] = item[1]
                        df.at[i, "description_BOM"] = item[2]
                        break

            # 추출할 인스턴스 객체
            instance_name = request.form.get("instance_name").upper()
            if instance_name:
                df = df[df["InstanName"].str.upper() == instance_name]

            file_count += 1  # 파일 카운트 증가
            result_filename = f"ICpin{file_count}.xlsx"
            result_filepath = os.path.join(app.root_path, "static", result_filename)

            # 엑셀 형식 변경
            grouped_data = df.groupby(
                [
                    "InstanName",
                    "value_BOM",
                    "description_BOM",
                    "value_NET",
                    "description_NET",
                ]
            )

            # 결과 데이터 생성
            result_data = pd.DataFrame(
                columns=[
                    "InstanName",
                    "value_BOM",
                    "description_BOM",
                    "value_NET",
                    "description_NET",  # 추가
                    "PinName",
                    "NetName",
                    "Connect Object",
                ]
            )
            for group, data in grouped_data:
                header_row = pd.DataFrame(
                    [group],
                    columns=[
                        "InstanName",
                        "value_BOM",
                        "description_BOM",
                        "value_NET",
                        "description_NET",
                    ],
                )
                data_columns = ["PinName", "NetName", "Connect Object"]
                data = data[data_columns]
                data = data.sort_values("PinName")  # PinPort 기준으로 정렬
                result_data = pd.concat([result_data, header_row, data])

            # 결과 엑셀 파일 생성
            result_data.to_excel(result_filepath, index=False)

            # 다운로드 링크 생성
            download_link = f"/static/{result_filename}"

            return jsonify({"result": "success", "download_link": download_link})


if __name__ == "__main__":
    app.run(debug=True)
