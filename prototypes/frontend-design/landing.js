/* PLANNING prototype. All tour and widget content is illustrative. */
window.landingMarkup = `
  <div class="landing-hero">
    <div class="landing-hero-copy">
      <span class="landing-kicker">HỖ TRỢ LỰA CHỌN TOUR</span>
      <h1 id="home-heading" tabindex="-1">Chọn kỹ,<br>đi thảnh thơi.</h1>
      <p>Đối chiếu tour theo nhu cầu, hiểu từng đánh đổi và kiểm chứng dữ kiện trước khi quyết định.</p>
      <div class="landing-hero-actions">
        <button class="btn btn-primary" type="button" data-nav="form">Tìm tour <span data-icon="arrow"></span></button>
        <a class="landing-guide-link" href="#how-it-works">Cách sử dụng <span aria-hidden="true">↘</span></a>
      </div>
    </div>
    <figure class="landing-hero-landscape">
      <div class="landing-landscape-frame"><img src="assets/fuji.jpg" alt="Núi Phú Sĩ và chùa Chureito, ảnh minh họa điểm đến" width="1000" height="667" fetchpriority="high"></div>
      <figcaption><span>Nhật Bản, một ý tưởng cho chuyến tới.</span><span>Ảnh minh họa điểm đến</span></figcaption>
    </figure>
  </div>

  <section class="landing-local" aria-labelledby="landing-local-title">
    <div class="landing-local-heading">
      <span data-icon="route"></span>
      <h2 id="landing-local-title">Trước khi lên đường</h2>
      <span class="landing-mock-label">Widget mô phỏng</span>
    </div>
    <div class="landing-location">
      <span class="landing-widget-label">Bạn đang ở đâu?</span>
      <p id="location-copy" role="status">Chưa xác định vị trí</p>
      <button class="landing-inline-action" type="button" data-location>Thử vị trí hiện tại <span data-icon="arrow"></span></button>
      <button class="landing-inline-action" type="button" data-location-denied>Thử khi từ chối quyền</button>
    </div>
    <div class="landing-weather">
      <span class="landing-widget-label">Thời tiết tại nơi khởi hành</span>
      <p id="weather-copy" role="status">Chọn vị trí để xem thời tiết minh họa.</p>
      <small>Dữ liệu mẫu, không phải dự báo thực tế.</small>
    </div>
  </section>

  <section class="landing-inspiration" aria-labelledby="landing-inspiration-title">
    <header class="landing-section-heading">
      <h2 id="landing-inspiration-title">Một nơi để bắt đầu.</h2>
      <p>Vài tour Nhật Bản minh họa. Nhu cầu của bạn sẽ là điểm xuất phát khi tìm và so sánh.</p>
    </header>
    <div class="landing-tour-grid">
      <article class="landing-tour landing-tour-wide">
        <div class="landing-tour-image"><img src="assets/tokyo.jpg" alt="Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến" width="1000" height="667" loading="lazy"></div>
        <div class="landing-tour-summary"><span class="landing-tour-place">NHẬT BẢN</span><span>5 ngày 4 đêm</span></div>
        <h3>Tokyo, Fuji &amp; Hakone</h3>
        <p>Thành phố, núi và một nhịp đi thư thả.</p>
        <div class="landing-tour-price"><span>32,8 triệu <small>/ người lớn</small></span><span class="landing-mock-label">Tour minh họa</span></div>
      </article>
      <article class="landing-tour">
        <div class="landing-tour-image"><img src="assets/kyoto.jpg" alt="Cổng torii đỏ tại Kyoto, ảnh minh họa điểm đến" width="1000" height="667" loading="lazy"></div>
        <div class="landing-tour-summary"><span class="landing-tour-place">NHẬT BẢN</span><span>6 ngày 5 đêm</span></div>
        <h3>Osaka, Kyoto &amp; Nara</h3>
        <p>Văn hóa, phố cổ và những ngôi đền.</p>
        <div class="landing-tour-price"><span>29,9 triệu <small>/ người lớn</small></span><span class="landing-mock-label">Tour minh họa</span></div>
      </article>
      <article class="landing-tour">
        <div class="landing-tour-image"><img src="assets/fuji.jpg" alt="Núi Phú Sĩ nhìn từ khu vực chùa Chureito, ảnh minh họa điểm đến" width="1000" height="667" loading="lazy"></div>
        <div class="landing-tour-summary"><span class="landing-tour-place">NHẬT BẢN</span><span>5 ngày 4 đêm</span></div>
        <h3>Tokyo, Fuji &amp; Yokohama</h3>
        <p>Góc nhìn khác giữa đô thị và cảnh núi.</p>
        <div class="landing-tour-price"><span>31,2 triệu <small>/ người lớn</small></span><span class="landing-mock-label">Tour minh họa</span></div>
      </article>
    </div>
    <div class="landing-inspiration-foot">
      <p>Giá mẫu chưa gồm mọi phụ thu; chưa phải gợi ý cá nhân hóa.</p>
      <button class="btn" type="button" data-demo-fill>Thử nhu cầu mẫu <span data-icon="arrow"></span></button>
    </div>
  </section>

  <section class="landing-guide" id="how-it-works" aria-labelledby="landing-guide-title">
    <header class="landing-section-heading">
      <h2 id="landing-guide-title">Hiểu lựa chọn trước khi chọn.</h2>
      <p>Đi cùng giúp bạn đối chiếu tour trọn gói theo cùng tiêu chí và nhìn rõ thông tin còn thiếu.</p>
    </header>
    <div class="landing-guide-layout">
      <ol class="landing-guide-steps">
        <li><span class="landing-guide-number" aria-hidden="true">1</span><div><h3>Kể điều bạn cần</h3><p>Điền thông tin chuyến đi, thêm URL tour hoặc ghi chú riêng nếu có.</p></div></li>
        <li><span class="landing-guide-number" aria-hidden="true">2</span><div><h3>Xác nhận và theo dõi</h3><p>Kiểm tra nhu cầu, rồi xem hệ thống đang thu thập và đối chiếu điều gì.</p></div></li>
        <li><span class="landing-guide-number" aria-hidden="true">3</span><div><h3>So sánh, hỏi thêm</h3><p>Mở nguồn từng dữ kiện, đọc phân tích AI và trao đổi để điều chỉnh nhu cầu.</p></div></li>
      </ol>
      <div class="landing-walkthrough">
        <div class="landing-walkthrough-title"><span data-icon="route"></span><h3>Xem một lượt tìm tour</h3><span class="landing-mock-label">Demo tương tác</span></div>
        <div id="walkthrough-scene" class="landing-story-scene" aria-live="polite" aria-atomic="true"><span class="landing-story-caption">Bắt đầu bằng nhu cầu của bạn</span><p>“Đi Nhật Bản từ TP.HCM, khoảng 5 ngày, ngân sách 35 triệu/người lớn.”</p><small>Minh họa cách sử dụng; chưa kết nối backend.</small></div>
        <div class="landing-walkthrough-foot"><span>Đi từng bước theo nhịp của bạn.</span><button class="btn" type="button" data-walkthrough>Chạy demo <span data-icon="arrow"></span></button></div>
      </div>
    </div>
  </section>
`;
