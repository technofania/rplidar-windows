// demo.frag - prosty wizual reagujacy na obiekty wykryte przez lidar.
//
// Wejscia:
//   sTD2DInputs[0] - poprzednia klatka (Feedback TOP) - zostawia smugi
//   sTD2DInputs[1] - 'objdata' z komponentu rplidar: R=x [m], G=y [m],
//                    B=szerokosc [m], A=1 gdy slot zajety
//
// Caly obraz to widok z gory: srodek kadru = czujnik, os Y w gore = przod
// czujnika. uRange mowi, ile metrow miesci sie od srodka do gory kadru.
//
// Czemu petla po teksturze, a nie po uniformach: tekstura ma tyle samo kodu
// dla 16 obiektow co dla 500, i nie trzeba nic przepisywac z CHOP-ow do
// uniformow co klatke.

uniform float uRange;    // metry od srodka do krawedzi kadru
uniform float uFade;     // 0..1, ile zostaje z poprzedniej klatki
uniform float uGlow;     // jasnosc poswiaty

out vec4 fragColor;

void main()
{
    vec2 uv = vUV.st;
    vec2 res = vec2(textureSize(sTD2DInputs[0], 0));
    float aspect = res.x / max(res.y, 1.0);

    // piksel -> metry w ukladzie czujnika
    vec2 p = (uv - 0.5) * 2.0 * uRange;
    p.x *= aspect;

    vec3 prev = texture(sTD2DInputs[0], uv).rgb * uFade;

    vec3 col = vec3(0.0);
    int n = textureSize(sTD2DInputs[1], 0).x;
    for (int i = 0; i < n; ++i) {
        vec4 o = texelFetch(sTD2DInputs[1], ivec2(i, 0), 0);
        if (o.a < 0.5) continue;

        float r = max(0.12, o.z * 0.5);          // promien z szerokosci obiektu
        float d = length(p - o.xy);
        float ring = exp(-pow(max(abs(d - r) - 0.01, 0.0) * 9.0, 2.0));
        float core = exp(-(d * d) / (r * r * 0.7));

        // kazdy slot dostaje swoj odcien, zeby bylo widac, ze numery sa trwale
        vec3 tint = 0.55 + 0.45 * cos(6.2831853 * (float(i) * 0.1731)
                                      + vec3(0.0, 2.094, 4.188));
        col += tint * (ring * 1.1 + core * 0.55);
    }

    fragColor = vec4(prev + col * uGlow, 1.0);
}
