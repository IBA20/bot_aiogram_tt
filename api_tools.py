import re
import aiohttp
from textwrap import dedent


currencies = {
    "AED": "United Arab Emirates Dirham",
    "BTC": "Bitcoin",
    "BYN": "New Belarusian Ruble",
    "CHF": "Swiss Franc",
    "CNY": "Chinese Yuan",
    "EUR": "Euro",
    "GBP": "British Pound Sterling",
    "GEL": "Georgian Lari",
    "KGS": "Kyrgystani Som",
    "KZT": "Kazakhstani Tenge",
    "RUB": "Russian Ruble",
    "UAH": "Ukrainian Hryvnia",
    "USD": "United States Dollar",
    "XAU": "Gold (troy ounce)",
}


async def get_weather(lat, lon, api_key):
    url = 'https://api.openweathermap.org/data/2.5/weather'
    params = {
        'lat': lat, 'lon': lon,
        'appid': api_key,
        'units': 'metric',
        'lang': 'ru',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            openweather = await response.json()
            if not response.ok:
                return 'Сервис недоступен в данный момент. Попробуйте позже.'
    wind_direction = {
        0: 'северный',
        45: 'северо-восточный',
        90: 'восточный',
        135: 'юго-восточный',
        180: 'южный',
        225: 'юго-западный',
        270: 'западный',
        315: 'северо-западный',
        360: 'северный',
    }
    weather_template = dedent(
        """
        Погода в вашей локации:
        {description}
        Температура: {temp}°
        Ветер: {wind_direction}, {wind_speed} м/с
        """
    )
    weather = weather_template.format(
        description=openweather.get('weather')[0].get('description'),
        temp=openweather.get('main').get('temp'),
        wind_direction=wind_direction.get(
            round(openweather.get('wind').get('deg') / 45) * 45
        ),
        wind_speed=openweather.get('wind').get('speed'),
    )
    return weather


async def convert_currency(
        base_currency: str, target_currency: str, amount: float, api_key
):
    url = 'https://api.apilayer.com/exchangerates_data/convert'
    params = {
        'from': base_currency,
        'to': target_currency,
        'amount': amount,
    }
    headers = {'apikey': api_key}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            conversion = await response.json()
            if not response.ok:
                return 'Сервис недоступен в данный момент. Попробуйте позже.'
    if not conversion.get('success'):
        return 'Обменный курс не найден'
    return f'{amount} {base_currency} = {conversion.get("result")} {target_currency}'


async def get_random_pet_url():
    url = 'https://mimimi.ru/random'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            page_content = await response.text()
            if not response.ok:
                return 'Сервис недоступен в данный момент. Попробуйте позже.'
            pet_url = re.search(
                r'https://3zvzd.blob.core.windows.net/mimimi/\d+\.jpg',
                page_content
            ).group(0)
            return pet_url
