from pathlib import Path
import json
import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

DATA_DIR = Path(__file__).parent / "data"
GEOJSON_PATH = Path(__file__).parent / "seoul_municipalities_geo_simple.json"
GEOJSON_URL = "https://raw.githubusercontent.com/southkorea/seoul-maps/refs/heads/master/juso/2015/json/seoul_municipalities_geo_simple.json"


COLOR_A = "#1f77b4"
COLOR_B = "#ff7f0e"
COLOR_SAME = "#7f3fbf"
COLOR_BASE = "#d9d9d9"


def flatten_coords(coords):
    """Polygon / MultiPolygon 좌표를 1차원 리스트로 펼칩니다."""
    if not coords:
        return []
    first = coords[0]
    if isinstance(first, (list, tuple)) and len(first) > 0 and isinstance(first[0], (int, float)):
        return [coords]

    flattened = []
    for item in coords:
        flattened.extend(flatten_coords(item))
    return flattened



def polygon_centroid_from_feature(feature):
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])
    rings = flatten_coords(coords)

    all_points = []
    for ring in rings:
        for point in ring:
            if len(point) >= 2:
                all_points.append(point[:2])

    if not all_points:
        return 126.9780, 37.5665

    arr = np.array(all_points)
    lon = float(arr[:, 0].mean())
    lat = float(arr[:, 1].mean())
    return lon, lat


@st.cache_data
def load_geojson():
    if not GEOJSON_PATH.exists():
        response = requests.get(GEOJSON_URL, timeout=30)
        response.raise_for_status()
        GEOJSON_PATH.write_text(response.text, encoding="utf-8")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    return geojson


@st.cache_data
def load_data():
    elderly = pd.read_csv(DATA_DIR / "고령자현황_내국인_구별_2024.csv")
    recipients = pd.read_csv(DATA_DIR / "2024_서울시_국민기초생활수급자_일반+생계+의료+구별_65세이상.csv")
    solitary_total = pd.read_csv(DATA_DIR / "독거노인_총.csv")
    solitary_low = pd.read_csv(DATA_DIR / "독거노인_저소득.csv")
    solitary_basic = pd.read_csv(DATA_DIR / "독거노인_기초수급.csv")

    solitary_total = solitary_total[["시군구", "전체수"]].rename(columns={"시군구": "자치구", "전체수": "독거노인_총"})
    solitary_low = solitary_low[["시군구", "전체수"]].rename(columns={"시군구": "자치구", "전체수": "저소득_독거노인"})
    solitary_basic = solitary_basic[["시군구", "전체수"]].rename(columns={"시군구": "자치구", "전체수": "기초수급_독거노인"})
    elderly = elderly.rename(columns={"고령자(내국인)수": "고령자수"})
    recipients = recipients.rename(columns={"총 수급자수": "노인수급자수"})

    df = elderly.merge(recipients, on="자치구")
    df = df.merge(solitary_total, on="자치구")
    df = df.merge(solitary_low, on="자치구")
    df = df.merge(solitary_basic, on="자치구")

    numeric_cols = ["고령자수", "노인수급자수", "독거노인_총", "저소득_독거노인", "기초수급_독거노인"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["독거노인 비율(%)"] = (df["독거노인_총"] / df["고령자수"] * 100).round(2)
    df["노인 수급자 비율(%)"] = (df["노인수급자수"] / df["고령자수"] * 100).round(2)
    df["저소득 독거노인 비율(%)"] = (df["저소득_독거노인"] / df["독거노인_총"] * 100).round(2)
    df["기초수급 독거노인 비율(%)"] = (df["기초수급_독거노인"] / df["독거노인_총"] * 100).round(2)
    df["고령자 대비 기초수급 독거노인 비율(%)"] = (df["기초수급_독거노인"] / df["고령자수"] * 100).round(2)

    target_cols = ["독거노인 비율(%)", "노인 수급자 비율(%)", "고령자 대비 기초수급 독거노인 비율(%)"]
    for col in target_cols:
        col_min, col_max = df[col].min(), df[col].max()
        if col_max == col_min:
            df[f"{col}_정규화"] = 0
        else:
            df[f"{col}_정규화"] = (df[col] - col_min) / (col_max - col_min)

    df["종합 취약지수"] = (
        df["독거노인 비율(%)_정규화"] * 0.35
        + df["노인 수급자 비율(%)_정규화"] * 0.35
        + df["고령자 대비 기초수급 독거노인 비율(%)_정규화"] * 0.30
    ) * 100
    df["종합 취약지수"] = df["종합 취약지수"].round(1)

    keep_cols = [
        "자치구",
        "고령자수",
        "노인수급자수",
        "독거노인_총",
        "저소득_독거노인",
        "기초수급_독거노인",
        "독거노인 비율(%)",
        "노인 수급자 비율(%)",
        "저소득 독거노인 비율(%)",
        "기초수급 독거노인 비율(%)",
        "고령자 대비 기초수급 독거노인 비율(%)",
        "종합 취약지수",
    ]
    return df[keep_cols]


@st.cache_data
def make_centroid_df(geojson):
    rows = []
    for feature in geojson["features"]:
        lon, lat = polygon_centroid_from_feature(feature)
        rows.append({
            "자치구": feature["properties"]["SIG_KOR_NM"],
            "lon": lon,
            "lat": lat,
        })
    return pd.DataFrame(rows)



def build_compare_map(geojson, map_df, district_a, district_b):
    fig = go.Figure()

    fig.add_trace(
        go.Choroplethmapbox(
            geojson=geojson,
            locations=map_df["자치구"],
            z=[0] * len(map_df),
            featureidkey="properties.SIG_KOR_NM",
            colorscale=[[0, COLOR_BASE], [1, COLOR_BASE]],
            showscale=False,
            marker_opacity=0.35,
            marker_line_width=0.8,
            hovertemplate="<b>%{location}</b><extra></extra>",
            name="기타 자치구",
            showlegend=False,
        )
    )

    if district_a == district_b:
        same_df = map_df[map_df["자치구"] == district_a]
        fig.add_trace(
            go.Choroplethmapbox(
                geojson=geojson,
                locations=same_df["자치구"],
                z=[1] * len(same_df),
                featureidkey="properties.SIG_KOR_NM",
                colorscale=[[0, COLOR_SAME], [1, COLOR_SAME]],
                showscale=False,
                marker_opacity=0.9,
                marker_line_width=2,
                hovertemplate=(
                    "<b>%{location}</b><br>"
                    + "종합 취약지수: %{customdata[0]:.1f}<br>"
                    + "독거노인 비율: %{customdata[1]:.2f}%<br>"
                    + "노인 수급자 비율: %{customdata[2]:.2f}%<extra></extra>"
                ),
                customdata=same_df[["종합 취약지수", "독거노인 비율(%)", "노인 수급자 비율(%)"]].to_numpy(),
                name=f"공통 선택 ({district_a})",
                showlegend=True,
            )
        )
    else:
        df_a = map_df[map_df["자치구"] == district_a]
        df_b = map_df[map_df["자치구"] == district_b]

        fig.add_trace(
            go.Choroplethmapbox(
                geojson=geojson,
                locations=df_a["자치구"],
                z=[1] * len(df_a),
                featureidkey="properties.SIG_KOR_NM",
                colorscale=[[0, COLOR_A], [1, COLOR_A]],
                showscale=False,
                marker_opacity=0.9,
                marker_line_width=2,
                hovertemplate=(
                    "<b>%{location}</b><br>"
                    + "종합 취약지수: %{customdata[0]:.1f}<br>"
                    + "독거노인 비율: %{customdata[1]:.2f}%<br>"
                    + "노인 수급자 비율: %{customdata[2]:.2f}%<extra></extra>"
                ),
                customdata=df_a[["종합 취약지수", "독거노인 비율(%)", "노인 수급자 비율(%)"]].to_numpy(),
                name=f"지역 A ({district_a})",
                showlegend=True,
            )
        )
        fig.add_trace(
            go.Choroplethmapbox(
                geojson=geojson,
                locations=df_b["자치구"],
                z=[1] * len(df_b),
                featureidkey="properties.SIG_KOR_NM",
                colorscale=[[0, COLOR_B], [1, COLOR_B]],
                showscale=False,
                marker_opacity=0.9,
                marker_line_width=2,
                hovertemplate=(
                    "<b>%{location}</b><br>"
                    + "종합 취약지수: %{customdata[0]:.1f}<br>"
                    + "독거노인 비율: %{customdata[1]:.2f}%<br>"
                    + "노인 수급자 비율: %{customdata[2]:.2f}%<extra></extra>"
                ),
                customdata=df_b[["종합 취약지수", "독거노인 비율(%)", "노인 수급자 비율(%)"]].to_numpy(),
                name=f"지역 B ({district_b})",
                showlegend=True,
            )
        )

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=9.8,
        mapbox_center={"lat": 37.565, "lon": 126.978},
        height=620,
        margin={"r": 0, "t": 10, "l": 0, "b": 0},
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01),
    )
    return fig



def main():
    st.set_page_config(page_title="서울시 노인 경제 취약층 시각화", page_icon="📊", layout="wide")

    st.title("서울시 노인 경제 취약층 시각화 대시보드")
    st.caption("고령자 수, 독거노인, 저소득 독거노인, 기초수급 독거노인을 자치구별로 비교합니다.")

    metric_map = {
        "종합 취약지수": "종합 취약지수",
        "노인 수급자 비율(%)": "노인 수급자 비율(%)",
        "독거노인 비율(%)": "독거노인 비율(%)",
        "고령자 대비 기초수급 독거노인 비율(%)": "고령자 대비 기초수급 독거노인 비율(%)",
        "저소득 독거노인 비율(%)": "저소득 독거노인 비율(%)",
        "기초수급 독거노인 비율(%)": "기초수급 독거노인 비율(%)",
    }
    bubble_size_map = {
        "독거노인 수": "독거노인_총",
        "저소득 독거노인 수": "저소득_독거노인",
        "기초수급 독거노인 수": "기초수급_독거노인",
        "고령자 수": "고령자수",
    }
    sort_map = {
        "종합 취약지수": "종합 취약지수",
        "노인 수급자 비율(%)": "노인 수급자 비율(%)",
        "독거노인 비율(%)": "독거노인 비율(%)",
        "저소득 독거노인 비율(%)": "저소득 독거노인 비율(%)",
        "기초수급 독거노인 비율(%)": "기초수급 독거노인 비율(%)",
        "독거노인 수": "독거노인_총",
    }
    scatter_metric_map = {
        "고령자 수": "고령자수",
        "노인 수급자 수": "노인수급자수",
        "독거노인 수": "독거노인_총",
        "저소득 독거노인 수": "저소득_독거노인",
        "기초수급 독거노인 수": "기초수급_독거노인",
        "독거노인 비율(%)": "독거노인 비율(%)",
        "노인 수급자 비율(%)": "노인 수급자 비율(%)",
        "저소득 독거노인 비율(%)": "저소득 독거노인 비율(%)",
        "기초수급 독거노인 비율(%)": "기초수급 독거노인 비율(%)",
        "고령자 대비 기초수급 독거노인 비율(%)": "고령자 대비 기초수급 독거노인 비율(%)",
        "종합 취약지수": "종합 취약지수",
    }

    with st.sidebar:
        st.header("분석 옵션")
        selected_metric_label = st.selectbox("지도 색상 기준", list(metric_map.keys()))
        selected_metric = metric_map[selected_metric_label]

        st.markdown("---")
        st.subheader("버블맵 옵션")
        bubble_size_label = st.radio("버블 크기", list(bubble_size_map.keys()), index=0)
        bubble_size_col = bubble_size_map[bubble_size_label]

        bubble_color_label = st.radio("버블 색상", list(metric_map.keys()), index=2)
        bubble_color_col = metric_map[bubble_color_label]

        st.markdown("---")
        sort_label = st.selectbox("표 정렬 기준", list(sort_map.keys()), index=0)
        sort_col = sort_map[sort_label]

    df = load_data()
    geojson = load_geojson()
    centroids = make_centroid_df(geojson)
    map_df = df.merge(centroids, on="자치구", how="left")

    total_elderly = int(df["고령자수"].sum())
    total_solitary = int(df["독거노인_총"].sum())
    total_basic = int(df["기초수급_독거노인"].sum())
    avg_index = round(df["종합 취약지수"].mean(), 1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("서울시 고령자 수", f"{total_elderly:,}명")
    c2.metric("서울시 독거노인 수", f"{total_solitary:,}명")
    c3.metric("서울시 기초수급 독거노인 수", f"{total_basic:,}명")
    c4.metric("평균 종합 취약지수", f"{avg_index}")

    tabs = st.tabs(["색상 지도", "버블맵", "표", "산점도", "지역 상세", "지역 비교", "사분면 분석", "지표 히트맵"])

    with tabs[0]:
        st.subheader("자치구별 색상 지도")
        st.write(f"현재 지도는 **{selected_metric_label}** 기준으로 색이 진해집니다.")

        fig_map = px.choropleth_mapbox(
            map_df,
            geojson=geojson,
            locations="자치구",
            featureidkey="properties.SIG_KOR_NM",
            color=selected_metric,
            color_continuous_scale="OrRd",
            mapbox_style="carto-positron",
            zoom=9.8,
            center={"lat": 37.565, "lon": 126.978},
            opacity=0.7,
            hover_name="자치구",
            hover_data={
                "고령자수": ":,",
                "노인수급자수": ":,",
                "독거노인_총": ":,",
                "저소득_독거노인": ":,",
                "기초수급_독거노인": ":,",
                "독거노인 비율(%)": True,
                "노인 수급자 비율(%)": True,
                "저소득 독거노인 비율(%)": True,
                "기초수급 독거노인 비율(%)": True,
                "종합 취약지수": True,
            },
        )
        fig_map.update_layout(margin={"r": 0, "t": 10, "l": 0, "b": 0}, height=650)
        st.plotly_chart(fig_map, use_container_width=True)
        st.info("해석 팁: 색이 진한 구일수록 선택한 지표가 높은 지역입니다.")

    with tabs[1]:
        st.subheader("자치구별 버블맵")
        st.write(f"버블 크기는 **{bubble_size_label}**, 색상은 **{bubble_color_label}** 기준입니다.")

        fig_bubble = px.scatter_mapbox(
            map_df,
            lat="lat",
            lon="lon",
            size=bubble_size_col,
            color=bubble_color_col,
            color_continuous_scale="YlOrRd",
            size_max=45,
            zoom=9.8,
            center={"lat": 37.565, "lon": 126.978},
            mapbox_style="carto-positron",
            hover_name="자치구",
            hover_data={
                "고령자수": ":,",
                "노인수급자수": ":,",
                "독거노인_총": ":,",
                "저소득_독거노인": ":,",
                "기초수급_독거노인": ":,",
                "독거노인 비율(%)": True,
                "노인 수급자 비율(%)": True,
                "종합 취약지수": True,
                "lat": False,
                "lon": False,
            },
        )
        fig_bubble.update_layout(margin={"r": 0, "t": 10, "l": 0, "b": 0}, height=650)
        st.plotly_chart(fig_bubble, use_container_width=True)
        st.info("해석 팁: 버블 크기와 색상을 따로 바꿔보면 절대 규모가 큰 지역과 비율이 높은 지역을 구분해 볼 수 있습니다.")

    with tabs[2]:
        st.subheader("자치구별 순위표")
        table_df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
        table_df.index = table_df.index + 1

        int_cols = ["고령자수", "노인수급자수", "독거노인_총", "저소득_독거노인", "기초수급_독거노인"]
        format_dict = {col: "{:,.0f}" for col in int_cols}
        format_dict.update({
            "독거노인 비율(%)": "{:.2f}",
            "노인 수급자 비율(%)": "{:.2f}",
            "저소득 독거노인 비율(%)": "{:.2f}",
            "기초수급 독거노인 비율(%)": "{:.2f}",
            "고령자 대비 기초수급 독거노인 비율(%)": "{:.2f}",
            "종합 취약지수": "{:.1f}",
        })

        styled_table = table_df.style.format(format_dict).background_gradient(cmap="Oranges", subset=[sort_col])
        st.dataframe(styled_table, use_container_width=True, height=600)

        top10 = table_df.head(10)
        fig_bar = px.bar(
            top10,
            x="자치구",
            y=sort_col,
            color=sort_col,
            color_continuous_scale="OrRd",
            text=sort_col,
            title=f"상위 10개 자치구 - {sort_label}",
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(height=500, margin={"r": 20, "t": 50, "l": 20, "b": 20})
        st.plotly_chart(fig_bar, use_container_width=True)

    with tabs[3]:
        st.subheader("지표 간 관계 보기")
        st.write("축, 버블 크기, 색상을 바꾸면서 어떤 자치구가 절대 규모와 상대 비율에서 동시에 높은지 탐색할 수 있습니다.")

        s1, s2 = st.columns(2)
        scatter_x_label = s1.selectbox("X축", list(scatter_metric_map.keys()), index=0)
        scatter_y_label = s2.selectbox("Y축", list(scatter_metric_map.keys()), index=6)
        s3, s4 = st.columns(2)
        scatter_size_label = s3.selectbox("버블 크기", list(scatter_metric_map.keys()), index=2)
        scatter_color_label = s4.selectbox("색상", list(scatter_metric_map.keys()), index=7)

        scatter_x = scatter_metric_map[scatter_x_label]
        scatter_y = scatter_metric_map[scatter_y_label]
        scatter_size = scatter_metric_map[scatter_size_label]
        scatter_color = scatter_metric_map[scatter_color_label]

        fig_scatter = px.scatter(
            df,
            x=scatter_x,
            y=scatter_y,
            size=scatter_size,
            color=scatter_color,
            hover_name="자치구",
            color_continuous_scale="YlOrRd",
            text="자치구",
            labels={
                scatter_x: scatter_x_label,
                scatter_y: scatter_y_label,
                scatter_size: scatter_size_label,
                scatter_color: scatter_color_label,
            },
        )
        fig_scatter.update_traces(textposition="top center")
        fig_scatter.update_layout(height=620)
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown(
            f"""
            **현재 해석 기준**
            - 오른쪽으로 갈수록 **{scatter_x_label}**이 높은 자치구입니다.
            - 위로 갈수록 **{scatter_y_label}**이 높은 자치구입니다.
            - 점이 클수록 **{scatter_size_label}** 규모가 큰 자치구입니다.
            - 색이 진할수록 **{scatter_color_label}** 수준이 높은 자치구입니다.
            """
        )

    with tabs[4]:
        st.subheader("지역 상세 분석")
        st.write("자치구 하나를 선택하면 해당 지역의 비율 지표를 서울 평균과 비교할 수 있습니다.")

        selected_district = st.selectbox("자치구 선택", sorted(df["자치구"].tolist()), key="detail_district")
        selected_row = df[df["자치구"] == selected_district].iloc[0]

        rate_cols = [
            "독거노인 비율(%)",
            "노인 수급자 비율(%)",
            "저소득 독거노인 비율(%)",
            "기초수급 독거노인 비율(%)",
            "고령자 대비 기초수급 독거노인 비율(%)",
        ]
        city_avg = df[rate_cols].mean().round(2)

        d1, d2, d3 = st.columns(3)
        d1.metric("선택 지역 종합 취약지수", f"{selected_row['종합 취약지수']:.1f}")
        d2.metric("선택 지역 고령자 수", f"{int(selected_row['고령자수']):,}명")
        d3.metric("선택 지역 독거노인 수", f"{int(selected_row['독거노인_총']):,}명")

        detail_compare = pd.DataFrame({
            "지표": rate_cols,
            selected_district: [selected_row[col] for col in rate_cols],
            "서울 평균": [city_avg[col] for col in rate_cols],
        })
        detail_long = detail_compare.melt(id_vars="지표", var_name="구분", value_name="값")

        fig_detail = px.bar(
            detail_long,
            x="지표",
            y="값",
            color="구분",
            barmode="group",
            text="값",
            title=f"{selected_district} vs 서울 평균",
        )
        fig_detail.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_detail.update_layout(height=520, margin={"r": 20, "t": 60, "l": 20, "b": 20})
        st.plotly_chart(fig_detail, use_container_width=True)

        rank_df = df[["자치구", "종합 취약지수"]].sort_values("종합 취약지수", ascending=False).reset_index(drop=True)
        rank = int(rank_df[rank_df["자치구"] == selected_district].index[0]) + 1
        st.info(f"{selected_district}의 종합 취약지수 순위는 서울 25개 자치구 중 {rank}위입니다.")

    with tabs[5]:
        st.subheader("지역 2개 비교")
        st.write("두 자치구를 선택하면 하나의 지도에서 서로 다른 색으로 위치를 표시하고, 아래에서 핵심 지표를 비교합니다.")

        compare_options = sorted(df["자치구"].tolist())
        c1, l1, c2, l2 = st.columns([4, 1.3, 4, 1.3])
        with c1:
            district_a = st.selectbox("첫 번째 자치구", compare_options, index=0, key="district_a")
        with l1:
            st.markdown(
                f"<div style='margin-top:2.1rem; font-size:0.95rem;'><span style='color:{COLOR_A}; font-size:1.25rem;'>■</span> 지역 A</div>",
                unsafe_allow_html=True,
            )
        with c2:
            district_b = st.selectbox("두 번째 자치구", compare_options, index=1, key="district_b")
        with l2:
            st.markdown(
                f"<div style='margin-top:2.1rem; font-size:0.95rem;'><span style='color:{COLOR_B}; font-size:1.25rem;'>■</span> 지역 B</div>",
                unsafe_allow_html=True,
            )

        fig_compare_map = build_compare_map(geojson, map_df, district_a, district_b)
        st.plotly_chart(fig_compare_map, use_container_width=True)

        compare_metrics = [
            "종합 취약지수",
            "독거노인 비율(%)",
            "노인 수급자 비율(%)",
            "저소득 독거노인 비율(%)",
            "기초수급 독거노인 비율(%)",
        ]

        row_a = df[df["자치구"] == district_a][["자치구"] + compare_metrics].copy()
        row_a["비교대상"] = f"지역 A ({district_a})"
        row_b = df[df["자치구"] == district_b][["자치구"] + compare_metrics].copy()
        row_b["비교대상"] = f"지역 B ({district_b})"
        compare_df = pd.concat([row_a, row_b], ignore_index=True)
        compare_long = compare_df.melt(id_vars=["자치구", "비교대상"], var_name="지표", value_name="값")

        fig_compare = px.bar(
            compare_long,
            x="지표",
            y="값",
            color="비교대상",
            barmode="group",
            text="값",
            title=f"{district_a} vs {district_b}",
            color_discrete_map={f"지역 A ({district_a})": COLOR_A, f"지역 B ({district_b})": COLOR_B},
        )
        fig_compare.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_compare.update_layout(height=520, margin={"r": 20, "t": 60, "l": 20, "b": 20})
        st.plotly_chart(fig_compare, use_container_width=True)

        if district_a == district_b:
            st.warning("같은 자치구를 두 번 선택했습니다. 다른 자치구를 선택하면 비교 효과가 더 커집니다.")

    with tabs[6]:
        st.subheader("사분면 분석")
        st.write("독거노인 비율과 노인 수급자 비율을 기준으로 자치구를 4개 유형으로 나눕니다.")

        x_col = "독거노인 비율(%)"
        y_col = "노인 수급자 비율(%)"
        x_mean = df[x_col].mean()
        y_mean = df[y_col].mean()

        quad_df = df.copy()
        quad_df["유형"] = np.select(
            [
                (quad_df[x_col] >= x_mean) & (quad_df[y_col] >= y_mean),
                (quad_df[x_col] >= x_mean) & (quad_df[y_col] < y_mean),
                (quad_df[x_col] < x_mean) & (quad_df[y_col] >= y_mean),
            ],
            [
                "고독거·고수급",
                "고독거·저수급",
                "저독거·고수급",
            ],
            default="저독거·저수급",
        )

        fig_quad = px.scatter(
            quad_df,
            x=x_col,
            y=y_col,
            size="고령자수",
            color="유형",
            hover_name="자치구",
            text="자치구",
            labels={x_col: x_col, y_col: y_col},
            title="사분면으로 보는 취약 지역 유형",
        )
        fig_quad.add_vline(x=x_mean, line_dash="dash")
        fig_quad.add_hline(y=y_mean, line_dash="dash")
        fig_quad.update_traces(textposition="top center")
        fig_quad.update_layout(height=650)

        st.plotly_chart(fig_quad, use_container_width=True)

        summary_quad = quad_df.groupby("유형")["자치구"].count().reset_index(name="자치구 수")
        st.dataframe(summary_quad, use_container_width=True)

        st.markdown(
            """
            **해석 기준**
            - **고독거·고수급**: 독거노인 비율과 수급자 비율이 모두 높아 우선 확인이 필요한 지역
            - **고독거·저수급**: 돌봄·고립 측면 이슈가 더 두드러질 수 있는 지역
            - **저독거·고수급**: 경제 취약성 측면이 상대적으로 더 큰 지역
            - **저독거·저수급**: 두 지표가 모두 평균보다 낮은 지역
            """
        )

    with tabs[7]:
        st.subheader("지표 히트맵")
        st.write("자치구별로 어떤 지표가 상대적으로 높은지 한 번에 확인할 수 있습니다.")

        heatmap_cols = [
            "종합 취약지수",
            "독거노인 비율(%)",
            "노인 수급자 비율(%)",
            "저소득 독거노인 비율(%)",
            "기초수급 독거노인 비율(%)",
            "고령자 대비 기초수급 독거노인 비율(%)",
        ]
        heatmap_df = df.set_index("자치구")[heatmap_cols]

        heatmap_norm = heatmap_df.copy()
        for col in heatmap_cols:
            col_min = heatmap_df[col].min()
            col_max = heatmap_df[col].max()
            if col_max == col_min:
                heatmap_norm[col] = 0
            else:
                heatmap_norm[col] = ((heatmap_df[col] - col_min) / (col_max - col_min) * 100).round(1)

        fig_heat = px.imshow(
            heatmap_norm.transpose(),
            aspect="auto",
            color_continuous_scale="OrRd",
            labels={"x": "자치구", "y": "지표", "color": "상대 수준(0~100)"},
            title="자치구별 주요 지표 히트맵",
        )
        fig_heat.update_layout(height=520)
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()
    st.subheader("처음 보는 사람을 위한 해석 예시")
    st.markdown(
        """
        1. **색상 지도**에서 지도 색상 기준을 바꿔가며 어떤 자치구가 계속 진하게 나타나는지 먼저 확인합니다.  
        2. **버블맵**에서 버블 크기와 버블 색상을 각각 바꿔 보며, 절대 규모가 큰 지역과 비율이 높은 지역이 같은지 다른지 비교합니다.  
        3. **지역 상세** 탭에서 관심 자치구를 하나 선택해 서울 평균보다 어떤 비율이 높은지 확인합니다.  
        4. **지역 비교** 탭에서 두 자치구를 선택해 하나의 지도에서 위치를 비교하고, 아래 막대그래프로 어떤 지표 차이가 큰지 봅니다.  
        5. **산점도**에서 축, 크기, 색상을 바꿔 보며 여러 지표가 동시에 높은 자치구가 어디인지 찾습니다.  

        이렇게 보면 한 지역의 **상대적 취약성**, **절대 규모**, **서울 평균과의 차이**, **다른 지역과의 비교**를 함께 볼 수 있습니다.
        """
    )


if __name__ == "__main__":
    main()
