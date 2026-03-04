import React from "react";

export default function SportSelect({ sport, setSport, level, setLevel, next }: any) {
  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <h2>종목 선택</h2>
      <select value={sport} onChange={(e) => setSport(e.target.value)}>
        <option value="ski">스키(MVP)</option>
        <option value="snowboard">스노우보드(준비중)</option>
        <option value="golf">골프(준비중)</option>
        <option value="running">런닝(준비중)</option>
      </select>

      <h3 style={{ marginTop: 16 }}>레벨</h3>
      <select value={level} onChange={(e) => setLevel(e.target.value)}>
        <option value="beginner">초보</option>
        <option value="intermediate">중급</option>
        <option value="advanced">상급</option>
      </select>

      <div style={{ marginTop: 24 }}>
        <button onClick={next}>다음</button>
      </div>
    </div>
  );
}
