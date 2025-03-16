import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import asyncio
import aiohttp
import concurrent.futures
import time
# Сопоставление месяцев с сезонами
month_to_season = {
    12: "Зима", 1: "Зима", 2: "Зима",
    3: "Весна", 4: "Весна", 5: "Весна",
    6: "Лето", 7: "Лето", 8: "Лето",
    9: "Осень", 10: "Осень", 11: "Осень"
}

# Функция для загрузки данных
def load_data(file):
    df = pd.read_csv(file, parse_dates=['timestamp'])
    return df

# Функция для анализа данных
def analyze_temperature(df, city):
    city_df = df[df['city'] == city].copy()
    # Преобразуем месяц в сезон
    city_df['season'] = city_df['timestamp'].dt.month.map(lambda x: month_to_season[x])
    # Считаем скользящее среднее и стандартное отклонение
    city_df['rolling_avg'] = city_df['temperature'].rolling(window=30, min_periods=1).mean()
    city_df['std_dev'] = city_df['temperature'].rolling(window=30, min_periods=1).std()
    # Расчет границ аномалии
    city_df['upper_bound'] = city_df['rolling_avg'] + 2 * city_df['std_dev']
    city_df['lower_bound'] = city_df['rolling_avg'] - 2 * city_df['std_dev']
    # Обнаружение аномалий
    city_df['anomaly'] = (city_df['temperature'] > city_df['upper_bound']) | (
            city_df['temperature'] < city_df['lower_bound'])
    return city_df

# Функция для параллельного анализа всех городов
# def analyze_all_cities(df):
#     cities = df['city'].unique()
#     with concurrent.futures.ThreadPoolExecutor() as executor:
#         results = list(executor.map(lambda city: analyze_temperature(df, city), cities))
#     return {city: result for city, result in zip(cities, results)}

# Асинхронная функция для получения температуры через OpenWeatherMap API
async def fetch_temperature_async(session, city, api_key):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    async with session.get(url) as response:
        return await response.json()

# Синхронная версия получения температуры
# def fetch_temperature_sync(city, api_key):
#     url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
#     response = requests.get(url)
#     return response.json()

# Функция для получения текущей температуры
async def get_current_temperature(city, api_key):
    async with aiohttp.ClientSession() as session:
        return await fetch_temperature_async(session, city, api_key)

def get_weather(city, api_key):
    return fetch_temperature_sync(city, api_key)

# Функция для отображения описательной статистики
def show_descriptive_statistics(city_df):
    st.write("### Описательная статистика")
    st.write(city_df.describe())


# Функция для отображения сезонных профилей
def show_seasonal_profiles(city_df):
    season_avg = city_df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    st.write("### Сезонные профили (среднее и стандартное отклонение)")
    st.write(season_avg)


# Основной интерфейс приложения
st.title("Анализ температур и климатических аномалий")
uploaded_file = st.file_uploader("Загрузите файл с историческими данными", type=["csv"])
if uploaded_file is not None:
    # Загружаем данные
    df = load_data(uploaded_file)
    cities = df['city'].unique()
    selected_city = st.selectbox("Выберите город", cities)
    # Анализ с замером времени выполнения
    # start_time = time.time()
    analyzed_data = analyze_temperature(df, selected_city)
    # st.write(f"Время выполнения анализа (без параллелизма): {time.time() - start_time:.2f} секунд")
    # start_time_1 = time.time()
    # all_analyzed_data = analyze_all_cities(df)
    # st.write(f"Время выполнения анализа (с параллелизмом): {time.time() - start_time_1:.2f} секунд")
    # Отображение графика температур и аномалий
    fig = px.line(analyzed_data, x='timestamp', y='temperature', title=f'Температура в {selected_city}',
                  labels={'temperature': '°C'}, line_shape='spline')
    fig.add_scatter(x=analyzed_data['timestamp'], y=analyzed_data['upper_bound'], mode='lines', name='Верхняя граница',
                    line=dict(dash='dot', color='blue', width=1.5), opacity=0.6)
    fig.add_scatter(x=analyzed_data['timestamp'], y=analyzed_data['lower_bound'], mode='lines', name='Нижняя граница',
                    line=dict(dash='dot', color='red', width=1.5), opacity=0.6)
    fig.add_scatter(x=analyzed_data[analyzed_data['anomaly']]['timestamp'],
                    y=analyzed_data[analyzed_data['anomaly']]['temperature'], mode='markers', name='Аномалии',
                    marker=dict(color='purple', size=10, symbol='circle'))
    st.plotly_chart(fig)
    # Отображение статистики и сезонных профилей
    show_descriptive_statistics(analyzed_data)
    show_seasonal_profiles(analyzed_data)

    # Ввод API-ключа для получения текущей температуры
    api_key = st.text_input("Введите ваш API-ключ OpenWeatherMap", type="password")
    if api_key:  # Если ключ введен
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # start = time.time()
        weather_data = loop.run_until_complete(get_current_temperature(selected_city, api_key))
        # st.write(f"asinch: , {time.time() - start:.2f}")
        # start1 = time.time()
        # weather_data_1 = get_weather(selected_city, api_key)
        # st.write(f"sinch: , {time.time() - start1:.2f}")
        # Проверяем, вернулся ли код 401 (неверный API-ключ)
        if weather_data.get("cod") == 401:
            st.error(
                '{"cod":401, "message": "Invalid API key. Please see https://openweathermap.org/faq#error401 for more info."}')
        elif "main" in weather_data:
            current_temp = weather_data["main"]["temp"]
            st.write(f"Текущая температура в {selected_city}: {current_temp}°C")

            # Проверяем, является ли текущая температура нормальной для сезона
            current_season = analyzed_data['season'].iloc[-1]
            season_avg = analyzed_data.groupby('season')['temperature'].agg(['mean', 'std']).loc[current_season]
            season_mean = season_avg['mean']
            season_std = season_avg['std']
            if season_mean - 2 * season_std <= current_temp <= season_mean + 2 * season_std:
                st.write(f"Текущая температура нормальна для сезона {current_season}.")
            else:
                st.write(f"Текущая температура аномальна для сезона {current_season}.")
        else:
            st.error("Ошибка при получении данных. Проверьте API-ключ.")


# После проведенного анализа, асинхронные методы использовать лучше,
# так как они работают быстрее. Однако параллельный процесс занимает больше времени.
# Вероятно, из-за того что данные небольшие, и накладные расходы на потоки оказываются значительными.


