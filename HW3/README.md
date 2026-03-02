# 아이디어 기반.

동화사 갓바위의 행랑 여기가 같이 뜨는 날싸가 있을 건데 그때를 찾아볼까. 그 데이터면 재밌을 거 가탕.

Oratory de 거기 그 뭐냐.. 그거.. 거기 같이 뜨고 지는 거.

내가 보는 달이랑 저기서 보는 달이 같은 거란 말야? 이거는 알고리즘 만들어야지?

근데 한쪽이 뜨는 거고 한쪽이 지는 해라는 게 재밌는 거 가탕.

달은 별로 좋은 아이디어가 아니야. 해달 뜨는것도 좋은 아이디어는 아닌거같애. 달은 그.. 해가 뜨는 그 의미랑은 조금 다른 거 같아.

날짜는 적어주는 게 나을듯. 여름 딱 한 철에만 나오는, 뭐 그런 재밌는 현상이니까.

지구 평평이랑은 다른 얘긴거같애.

다른 지역들 몇 개 더 넣는 수준은 될듯. 성당기준 /  학교기준이랑 <-> 집 가고 싶은 애들 있을 거 같으니까. 이 정도는 그릴 수 있을듯.

이 지역들은 그런 거임. 어차피 먼 애들이니까 거의 같은 해를 못 보고 사는 사람들이니까 가능하다면서 발표 때 그런 식으로 가야지.



# 구현
  1. 위치(위도/경도) 데이터를 정한다.
  2. 일출/일몰 데이터를 받아서, 같은 절대 시점(UTC)에서 한쪽은 뜨고 한쪽은 지는 날짜/시간을 찾는다.

일단 일출 일몰 데이터를 리소스로 받아옴. from meteo (이거 공짜 ip임.)
애초에 그런 현상이 나타나는 날짜를 오히려 역으로 찾는 거야. 날짜와 시간을. 예를 들어서 몬트리올과 베이징 같은 경우에는 같은 시점 (그러니까 절대적인 시점인거야. 그쪽에서는 아침이니까 해가 뜨고 몬트리올에서는 저녁이니까 해가 지고 하는 그 시점)의 날짜와 시간을 구하는 거지. 
 맞아. 그리고 중복일 수 있거든? 여러 날짜가 있을 수 있어. 그렇다면 음... 연도 기준 최신 우선, 그 다음엔 같은 연도에 여러 개 있다면 아까 말한 diff
  기준 가까운 거 우선으로 해줘. 판정은 +-10분 정도로만 해도 충분하더라고. diff까지 분 단위로 같으면 그 다음엔 둘 중 최근인걸로 해줘.

  3. 각 위치의 시각 자료(스트리트뷰/사진)를 가져온다.
  4. 두 이미지를 라인 스케치 스타일로 변환하고 합성한다.
  5. 해 위치를 시각적으로 강조해서 최종 결과 이미지를 만든다.


구글 api 넣어서 위치 정보 구하기 -> 일출 일몰 시간 데이터 구하기,

위도 경도 데이터는 구글 맵스 이런 데 찍으면 나오니까 그거 기반으로 구하기.

그 다음에 해당 구글 api 넣으면 ? 해당 위도 경도 데이터 쓸 수 있음?

그리고 그러면 스트리트뷰를 얻을 수 있는 거지. 해당 위치에서. 정동이든 정남이든 정서든, 그냥 중간에 오게 하자.

그 다음에 음... 그거 기반으로 openai api 써서 그림을 그리는 거야. 해당 위치 사진들 받아와서 "미니멀 라인 스케치로 그려줘" 라고 하는 거임.

그리고 두 장 이어붙이는 건 같이.

그러면 이제 거기다가 해 위치를 합성하는거임. 중앙이고 양 사진에 해가 걸쳐진 (sunrise/set인지는 헷갈리게?) 사진을 미니멀 라인 스케치로, 붉게 그려달라고 하는 거야. 이 정도면 괜찮을거같애.

그러면 같은 지역, 같은 시간인데, 한 쪽은 뜨는 해고, 한 쪽은 지는 해를 볼 수가 있을 것 같아.


구글 api 넣어서 위치 정보 찍기 + 스트릿 뷰 얻어오기 + 
실제로 쓸 수 있는 위치 하나 잡아오기 -> 이거는 그냥 위도 경도 정도 얻어오면 되겠다. 그냥 확실하진 않은데 음.. 그냥 검색으로도 되게 할 수도 있지 않을까?
출발점 도착점 그런 걸로.

그리고 


## MET Sunrise/Sunset (Free API)

```bash
python HW3/utils/met_sun.py \
  --lat 45.5017 --lon -73.5673 \
  --start 2026-03-01 --end 2026-03-05 \
  --offset +00:00 \
  --output HW3/montreal_sun_times.csv
```

- `utils/met_sun.py`는 MET Norway Sunrise API를 사용합니다.
- CSV에는 `sunrise/sunset` 시간과 함께 `sunrise_azimuth/sunset_azimuth`(방위각)도 저장됩니다.

## Street View Pair (Step 3)

```bash
# 1) Fill key in HW3/.env (template: HW3/.env.example)
# GOOGLE_MAPS_API_KEY=YOUR_KEY

# 2) Run
python HW3/fetch_streetview_pair.py \
  --name-a Montreal --lat-a 45.5017 --lon-a -73.5673 --heading-a 120 --pitch-a 0 \
  --name-b Beijing --lat-b 39.9042 --lon-b 116.4074 --heading-b 260 --pitch-b 0 \
  --size 1024x768 --fov 90 --radius 50 \
  --outdir HW3/streetview_outputs
```

- 결과물은 `streetview_outputs` 폴더에 실제 사진(`*.jpg`)과 메타데이터(`*_metadata.json`)로 저장됩니다.

## One-Shot: Match Date + Sun Direction + Street View

```bash
python HW3/find_and_fetch_sun_streetview.py \
  --name-a PohangSunrise \
  --maps-url-a "YOUR_GOOGLE_MAPS_URL_A" \
  --event-a sunrise --tz-a Asia/Seoul \
  --name-b MontrealSunset \
  --maps-url-b "YOUR_GOOGLE_MAPS_URL_B" \
  --event-b sunset --tz-b America/Toronto \
  --start 2026-01-01 --end 2026-12-31 --tol-min 10 \
  --match-index 1 \
  --radius 50 --source default \
  --outdir HW3/streetview_outputs/pohang_montreal
```

- 위 스크립트는 `Google Maps URL -> 좌표 추출 -> 매칭 날짜 탐색 -> 해당 날짜 일출/일몰 방위각 heading 계산 -> Street View 저장`을 한 번에 수행합니다.
