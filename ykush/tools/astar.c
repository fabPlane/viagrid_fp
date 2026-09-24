/* A* core for router.py (two layers, 8 directions, direction-aware turn cost,
 * layer changes only at allowed via cells). Built on demand by router.py:
 *   gcc -O2 -shared -fPIC -o _astar.so astar.c
 */
#include <stdint.h>
#include <stdlib.h>
#include <math.h>

typedef struct { float f; int32_t s; } node;

static node *heap; static int hn, hcap;

static void push(float f, int32_t s) {
    if (hn == hcap) { hcap = hcap ? hcap * 2 : 1 << 16; heap = realloc(heap, sizeof(node) * hcap); }
    int i = hn++;
    while (i > 0) {
        int p = (i - 1) / 2;
        if (heap[p].f <= f) break;
        heap[i] = heap[p]; i = p;
    }
    heap[i].f = f; heap[i].s = s;
}

static node pop(void) {
    node top = heap[0], last = heap[--hn];
    int i = 0;
    for (;;) {
        int c = 2 * i + 1;
        if (c >= hn) break;
        if (c + 1 < hn && heap[c + 1].f < heap[c].f) c++;
        if (heap[c].f >= last.f) break;
        heap[i] = heap[c]; i = c;
    }
    heap[i] = last;
    return top;
}

static const int DX[8] = {1, 1, 0, -1, -1, -1, 0, 1};
static const int DY[8] = {0, 1, 1, 1, 0, -1, -1, -1};

/* blk, goal: [2][H][W] uint8; via_ok: [H][W] uint8; heur: [H][W] float (mm).
 * mult: [2][H][W] float >= 1, cost multiplier per mm entering a cell.
 * src: nsrc triples (layer, y, x). Output: path of cell ids (layer*H*W + y*W + x), start->goal.
 * Returns path length, -1 if no path, -2 if out buffer too small, -3 if expansion limit hit. */
int astar(int H, int W, const uint8_t *blk, const uint8_t *via_ok, const float *heur,
          const uint8_t *goal, const int32_t *src, int nsrc, float res, float via_cost,
          float turn_cost, int max_exp, int32_t *out, int cap, const float *mult) {
    const long HW = (long)H * W, N = 16 * HW;
    float *g = malloc(sizeof(float) * N);
    int32_t *par = malloc(sizeof(int32_t) * N);
    uint8_t *closed = calloc(N, 1);
    for (long i = 0; i < N; i++) g[i] = INFINITY;
    hn = 0;
    for (int k = 0; k < nsrc; k++) {
        int L = src[3 * k], y = src[3 * k + 1], x = src[3 * k + 2];
        if (blk[L * HW + (long)y * W + x]) continue;
        for (int d = 0; d < 8; d++) {
            int32_t s = (int32_t)(((long)(L * 8 + d) * H + y) * W + x);
            g[s] = 0; par[s] = -1;
            push(heur[(long)y * W + x], s);
        }
    }
    int32_t found = -1; long nexp = 0; int rc = -1;
    while (hn) {
        node nd = pop();
        int32_t s = nd.s;
        if (closed[s]) continue;
        closed[s] = 1;
        long rem = s;
        int x = rem % W; rem /= W;
        int y = rem % H; rem /= H;
        int d = rem % 8; int L = rem / 8;
        if (goal[L * HW + (long)y * W + x]) { found = s; break; }
        if (++nexp > max_exp) { rc = -3; break; }
        float gc = g[s];
        for (int nd2 = 0; nd2 < 8; nd2++) {
            int turn = (nd2 - d + 8) % 8; if (turn > 4) turn = 8 - turn;
            if (turn > 2) continue;
            int jx = x + DX[nd2], jy = y + DY[nd2];
            if (jx < 0 || jy < 0 || jx >= W || jy >= H) continue;
            if (blk[L * HW + (long)jy * W + jx]) continue;
            if (DX[nd2] && DY[nd2] && (blk[L * HW + (long)y * W + jx] || blk[L * HW + (long)jy * W + x])) continue;
            float c = gc + res * ((DX[nd2] && DY[nd2]) ? 1.41421356f : 1.0f) * mult[L * HW + (long)jy * W + jx]
                      + turn_cost * turn;
            int32_t t = (int32_t)(((long)(L * 8 + nd2) * H + jy) * W + jx);
            if (c < g[t]) { g[t] = c; par[t] = s; push(c + heur[(long)jy * W + jx], t); }
        }
        if (via_ok[(long)y * W + x]) {
            int L2 = 1 - L;
            if (!blk[L2 * HW + (long)y * W + x]) {
                int32_t t = (int32_t)(((long)(L2 * 8 + d) * H + y) * W + x);
                float c = gc + via_cost;
                if (c < g[t]) { g[t] = c; par[t] = s; push(c + heur[(long)y * W + x], t); }
            }
        }
    }
    if (found >= 0) {
        int n = 0;
        for (int32_t s = found; s >= 0; s = par[s]) n++;
        if (n > cap) rc = -2;
        else {
            int i = n - 1;
            for (int32_t s = found; s >= 0; s = par[s]) {
                long rem = s;
                int x = rem % W; rem /= W;
                int y = rem % H; rem /= H;
                int L = (rem) / 8;
                out[i--] = (int32_t)(L * HW + (long)y * W + x);
            }
            rc = n;
        }
    }
    free(g); free(par); free(closed);
    return rc;
}
