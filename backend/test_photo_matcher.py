"""photo_matcher 동작 확인용 스크립트 (네트워크/DB 불필요).

실행: python test_photo_matcher.py
"""
from datetime import datetime, timedelta

from app.services.photo_matcher import Photo, Slot, assign, fallback_slots, score


def main() -> None:
    slots = [
        Slot(index=0, after_paragraph=1, need="병원 외관 또는 로비", keywords=["외관", "간판", "로비"], stage="도입"),
        Slot(index=1, after_paragraph=3, need="의사 상담 장면", keywords=["상담", "의사", "진료실"], stage="진료과정"),
        Slot(index=2, after_paragraph=5, need="피부 시술 장면", keywords=["피부", "시술", "레이저"], stage="시술"),
        Slot(index=3, after_paragraph=7, need="장비 클로즈업", keywords=["레이저", "장비"], stage="장비소개"),
        Slot(index=4, after_paragraph=9, need="마무리 안내", keywords=["대기실", "안내"], stage="마무리"),
    ]

    now = datetime(2026, 9, 3, 12, 0, 0)
    photos = [
        Photo(id="p-exterior", scene="exterior", tags=["건물 외관", "간판", "실외", "맑은 날"],
              suitable_for=["도입", "마무리"], use_count=0),
        Photo(id="p-lobby", scene="reception", tags=["로비", "대기실", "실내", "밝은 톤", "안내문"],
              has_text=True, suitable_for=["도입", "마무리"], use_count=3),
        Photo(id="p-consult", scene="consult", tags=["진료실", "의사", "상담", "모니터"],
              suitable_for=["진료과정"], use_count=1),
        Photo(id="p-staff", scene="staff", tags=["의료진", "직원", "미소", "실내"],
              suitable_for=["도입", "진료과정"], use_count=5),
        Photo(id="p-laser", scene="treatment", tags=["피부 시술", "레이저", "치료실", "환자 손"],
              suitable_for=["시술"], use_count=0),
        Photo(id="p-device", scene="equipment", tags=["레이저 장비", "기기", "클로즈업", "패널 글자"],
              has_text=True, suitable_for=["장비소개", "시술"], use_count=2),
        Photo(id="p-herbal", scene="herbal", tags=["한약재", "약재실", "갈색 톤"],
              suitable_for=["진료과정"], use_count=0),
        Photo(id="p-product", scene="product", tags=["제품", "패키지", "화이트 톤"],
              suitable_for=["마무리"], use_count=0, last_used_at=now - timedelta(days=1)),
    ]

    print("=== score 샘플 ===")
    print("도입 x p-exterior      :", round(score(slots[0], photos[0], set()), 3))
    print("도입 x p-lobby(has_text):", round(score(slots[0], photos[1], set()), 3))
    print("장비소개 x p-device    :", round(score(slots[3], photos[5], set()), 3))
    print("마무리 x p-product(최근):", round(score(slots[4], photos[7], {"p-product"}), 3))

    print()
    print("=== assign (5 슬롯 / 8 사진, p-product 최근 사용) ===")
    result = assign(slots, photos, recently_used_ids={"p-product"})
    for r in result:
        print(r)
    ids = [r["pool_image_id"] for r in result]
    assert len(result) == 5, result
    assert len(set(ids)) == 5, "사진 중복 배정"
    assert [r["slot"] for r in result] == [0, 1, 2, 3, 4]
    assert result[0]["pool_image_id"] == "p-exterior"
    assert result[1]["pool_image_id"] == "p-consult"
    assert result[2]["pool_image_id"] == "p-laser"
    assert result[3]["pool_image_id"] == "p-device"

    print()
    print("=== assign (5 슬롯 / 3 사진, allow_repeat=True) ===")
    few = photos[:3]
    result2 = assign(slots, few, allow_repeat=True)
    for r in result2:
        print(r)
    assert len(result2) == 5
    assert len(set(r["pool_image_id"] for r in result2)) == 3

    print()
    print("=== assign (5 슬롯 / 3 사진, allow_repeat=False) ===")
    result3 = assign(slots, few, allow_repeat=False)
    print([(r["slot"], r["pool_image_id"]) for r in result3])
    assert len(result3) == 3

    assert assign(slots, []) == []
    assert assign([], photos) == []

    print()
    print("=== fallback_slots(9, 4) ===")
    fb = fallback_slots(9, 4)
    for s in fb:
        print(s)
    assert [s.after_paragraph for s in fb] == [2, 4, 5, 7], [s.after_paragraph for s in fb]
    assert [s.stage for s in fb] == ["도입", "진료과정", "시술", "마무리"]

    print()
    print("=== fallback_slots 경계 ===")
    print("fallback_slots(3, 10):", [(s.after_paragraph, s.stage) for s in fallback_slots(3, 10)])
    print("fallback_slots(1, 1) :", [(s.after_paragraph, s.stage) for s in fallback_slots(1, 1)])
    print("fallback_slots(0, 4) :", fallback_slots(0, 4))
    assert fallback_slots(0, 4) == []
    assert fallback_slots(5, 0) == []

    print()
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
