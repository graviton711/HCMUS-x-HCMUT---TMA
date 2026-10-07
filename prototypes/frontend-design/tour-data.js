"use strict";
// Shared synthetic tours and fields for comparison and local source sections.
const tours = {
  a:{id:"a",name:"Tokyo · Fuji · Hakone",provider:"Lữ hành Mẫu A",photo:"fuji.jpg",alt:"Núi Phú Sĩ và chùa Chureito, ảnh minh họa điểm đến",start:"10/11/2026",days:"5 ngày 4 đêm",price:32800000,tag:"Cân bằng các ưu tiên",reason:"5 ngày, không có điểm mua sắm trong lịch trình mẫu.",caution:"Phụ thu phòng đơn chưa được công bố.",route:"Tokyo · Fuji · Hakone",included:"Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình",shopping:"Không có trong lịch trình công bố",extras:"Phòng đơn chưa công bố",cancel:"Trước 30 ngày: phí 20% giá tour",quality:"Một phần",offers:[{start:"10/11/2026",price:32800000},{start:"17/11/2026",price:34800000}]},
  b:{id:"b",name:"Osaka · Kyoto · Nara",provider:"Lữ hành Mẫu B",photo:"kyoto.jpg",alt:"Cổng torii đỏ tại Kyoto, ảnh minh họa điểm đến",start:"11/11/2026",days:"6 ngày 5 đêm",price:29900000,tag:"Ưu tiên giá công bố",reason:"Giá công bố thấp hơn trong nhóm, nhiều điểm tham quan.",caution:"6 ngày và 2 điểm mua sắm theo lịch trình.",route:"Osaka · Kyoto · Nara",included:"Vé bay khứ hồi, 5 đêm khách sạn, bữa ăn theo lịch trình",shopping:"2 điểm theo lịch trình",extras:"Phòng đơn: 4.200.000 ₫",cancel:"Trước 30 ngày: phí 30% giá tour",quality:"Một phần"},
  c:{id:"c",name:"Tokyo · Fuji · Yokohama",provider:"Lữ hành Mẫu C",photo:"tokyo.jpg",alt:"Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến",start:"12/11/2026",days:"5 ngày 4 đêm",price:31200000,tag:"Ưu tiên thời lượng",reason:"5 ngày, giá công bố nằm trong khoảng ưu tiên.",caution:"Chính sách hủy và phụ thu còn thiếu dữ kiện.",route:"Tokyo · Fuji · Yokohama",included:"Vé bay, khách sạn; bữa ăn chưa rõ",shopping:"1 điểm theo lịch trình",extras:null,cancel:null,quality:"Một phần"},
  d:{id:"d",name:"Tokyo · Kamakura · Fuji",provider:"Lữ hành Mẫu D",photo:"tokyo.jpg",alt:"Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến",start:"13/11/2026",days:"5 ngày 4 đêm",price:33400000,tag:"Cân bằng các ưu tiên",reason:"5 ngày, không có điểm mua sắm trong lịch trình mẫu.",caution:"Cần xác nhận mức phụ thu phòng đơn.",route:"Tokyo · Kamakura · Fuji",included:"Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình",shopping:"Không có trong lịch trình công bố",extras:null,cancel:"Trước 30 ngày: phí 20% giá tour",quality:"Một phần"},
  e:{id:"e",name:"Osaka · Kyoto · Kobe",provider:"Lữ hành Mẫu E",photo:"kyoto.jpg",alt:"Cổng torii đỏ tại Kyoto, ảnh minh họa điểm đến",start:"14/11/2026",days:"6 ngày 5 đêm",price:30500000,tag:"Ưu tiên giá công bố",reason:"Giá công bố thấp hơn trong nhóm minh họa mới.",caution:"6 ngày và 1 điểm mua sắm theo lịch trình.",route:"Osaka · Kyoto · Kobe",included:"Vé bay khứ hồi, 5 đêm khách sạn, bữa ăn theo lịch trình",shopping:"1 điểm theo lịch trình",extras:"Phòng đơn: 4.000.000 ₫",cancel:"Trước 30 ngày: phí 25% giá tour",quality:"Một phần"},
  f:{id:"f",name:"Tokyo · Hakone · Nikko",provider:"Lữ hành Mẫu F",photo:"tokyo.jpg",alt:"Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến",start:"15/11/2026",days:"5 ngày 4 đêm",price:31900000,tag:"Ưu tiên thời lượng",reason:"5 ngày, giá công bố nằm trong khoảng ưu tiên.",caution:"Chính sách hủy chưa được công bố.",route:"Tokyo · Hakone · Nikko",included:"Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình",shopping:"1 điểm theo lịch trình",extras:"Phòng đơn: 3.800.000 ₫",cancel:null,quality:"Một phần"},
  ref:{id:"ref",name:"Tokyo · Fuji · Osaka",provider:"Lữ hành Tham chiếu",photo:"fuji.jpg",alt:"Núi Phú Sĩ và chùa Chureito, ảnh minh họa điểm đến",start:"10/11/2026",days:"5 ngày 4 đêm",price:35900000,tag:"Bạn cung cấp",reason:"Tour bạn gửi được giữ để đối chiếu.",caution:"Giá công bố cao hơn khoảng ưu tiên.",route:"Tokyo · Fuji · Osaka",included:"Vé bay, 4 đêm khách sạn; bữa ăn chưa rõ",shopping:null,extras:"Phòng đơn chưa công bố",cancel:"Trước 30 ngày: phí 30% giá tour",quality:"Một phần"}
};
const groups = [["a","b","c"],["d","e","f"]];
const fields = [
  {key:"provider",label:"Nhà cung cấp",hint:"Nhận diện theo nguồn"},
  {key:"price",label:"Giá công bố",hint:"VND / người lớn"},
  {key:"dates",label:"Lịch & thời lượng",hint:"Chưa xác nhận còn chỗ"},
  {key:"route",label:"Lịch trình",hint:"Các điểm đến công bố"},
  {key:"included",label:"Bao gồm",hint:"Theo lịch đang xem"},
  {key:"shopping",label:"Điểm mua sắm",hint:"Ưu tiên của bạn"},
  {key:"extras",label:"Phụ thu",hint:"Ngoài giá công bố"},
  {key:"cancel",label:"Hủy / đổi",hint:"Cần đọc điều kiện"},
  {key:"quality",label:"Dữ liệu & nguồn",hint:"Theo từng dữ kiện"}
];
