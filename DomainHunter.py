import java.io.*;
import java.net.*;
import java.net.http.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.*;

public class DomainHunter {

    // ===== CONFIG =====
    private static final int THREADS = 60;
    private static final int TIMEOUT = 5;
    private static final String OUTPUT_FILE = "live_subdomains.txt";

    private static final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(TIMEOUT))
            .build();

    // ===== BANNER =====
    public static void banner() {
        System.out.println(
            "██╗    ██╗██╗███╗   ██╗████████╗███████╗██████╗ \n" +
            "██║    ██║██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗\n" +
            "██║ █╗ ██║██║██╔██╗ ██║   ██║   █████╗  ██████╔╝\n" +
            "██║███╗██║██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗\n" +
            "╚███╔███╔╝██║██║ ╚████║   ██║   ███████╗██║  ██║\n" +
            " ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝\n\n" +
            "        ⚡ winter AKI - DomainHunter ⚡\n" +
            "        [ Recon | Scan | Hunt | Exploit ]\n" +
            "=================================================\n"
        );
    }

    // ===== CLEAN DOMAIN =====
    public static String cleanDomain(String domain, String base) {
        domain = domain.trim().toLowerCase();
        domain = domain.replace("*.", "");
        domain = domain.split("/")[0];
        domain = domain.split(":")[0];

        if (domain.matches("^[a-z0-9.-]+\\.[a-z]{2,}$") && domain.endsWith(base)) {
            return domain;
        }
        return null;
    }

    // ===== HTTP GET =====
    public static String httpGet(String url) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .GET()
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            return response.body();
        } catch (Exception e) {
            return null;
        }
    }

    // ===== SOURCES =====
    public static Set<String> crtsh(String domain) {
        Set<String> results = new HashSet<>();
        try {
            String body = httpGet("https://crt.sh/?q=%25." + domain + "&output=json");

            if (body != null) {
                Matcher m = Pattern.compile("\"name_value\":\"(.*?)\"").matcher(body);

                while (m.find()) {
                    String[] subs = m.group(1).split("\\\\n");
                    for (String s : subs) {
                        String c = cleanDomain(s, domain);
                        if (c != null) results.add(c);
                    }
                }
            }
        } catch (Exception ignored) {}
        return results;
    }

    public static Set<String> alienvault(String domain) {
        Set<String> results = new HashSet<>();
        try {
            String body = httpGet("https://otx.alienvault.com/api/v1/indicators/domain/" + domain + "/passive_dns");

            if (body != null) {
                Matcher m = Pattern.compile("\"hostname\":\"(.*?)\"").matcher(body);

                while (m.find()) {
                    String c = cleanDomain(m.group(1), domain);
                    if (c != null) results.add(c);
                }
            }
        } catch (Exception ignored) {}
        return results;
    }

    public static Set<String> bufferover(String domain) {
        Set<String> results = new HashSet<>();
        try {
            String body = httpGet("https://dns.bufferover.run/dns?q=." + domain);

            if (body != null) {
                Matcher m = Pattern.compile(",([a-zA-Z0-9.-]+\\." + domain + ")").matcher(body);

                while (m.find()) {
                    String c = cleanDomain(m.group(1), domain);
                    if (c != null) results.add(c);
                }
            }
        } catch (Exception ignored) {}
        return results;
    }

    // ===== DNS =====
    public static boolean resolve(String domain) {
        try {
            InetAddress.getByName(domain);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // ===== HTTP CHECK =====
    public static String checkHttp(String domain) {
        for (String scheme : new String[]{"https://", "http://"}) {
            try {
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(scheme + domain))
                        .timeout(java.time.Duration.ofSeconds(TIMEOUT))
                        .GET()
                        .build();

                HttpResponse<Void> response = client.send(request, HttpResponse.BodyHandlers.discarding());
                return scheme + domain + " [" + response.statusCode() + "]";
            } catch (Exception ignored) {}
        }
        return null;
    }

    // ===== MAIN =====
    public static void main(String[] args) throws Exception {

        banner();

        if (args.length < 1) {
            System.out.println("Usage: java DomainHunter example.com");
            return;
        }

        String domain = args[0];
        System.out.println("[+] Target: " + domain + "\n");

        ExecutorService executor = Executors.newFixedThreadPool(THREADS);

        // ===== COLLECT =====
        Set<String> subs = ConcurrentHashMap.newKeySet();

        List<Callable<Void>> tasks = List.of(
                () -> { subs.addAll(crtsh(domain)); return null; },
                () -> { subs.addAll(alienvault(domain)); return null; },
                () -> { subs.addAll(bufferover(domain)); return null; }
        );

        executor.invokeAll(tasks);
        System.out.println("[+] Found: " + subs.size());

        // ===== RESOLVE =====
        List<String> live = Collections.synchronizedList(new ArrayList<>());

        List<Callable<Void>> resolveTasks = new ArrayList<>();
        for (String sub : subs) {
            resolveTasks.add(() -> {
                if (resolve(sub)) live.add(sub);
                return null;
            });
        }

        executor.invokeAll(resolveTasks);
        System.out.println("[+] Live: " + live.size());

        // ===== HTTP =====
        List<String> active = Collections.synchronizedList(new ArrayList<>());

        List<Callable<Void>> httpTasks = new ArrayList<>();
        for (String sub : live) {
            httpTasks.add(() -> {
                String res = checkHttp(sub);
                if (res != null) {
                    System.out.println(res);
                    active.add(res);
                }
                return null;
            });
        }

        executor.invokeAll(httpTasks);
        executor.shutdown();

        // ===== SAVE =====
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(OUTPUT_FILE))) {
            for (String a : active) writer.write(a + "\n");
        }

        System.out.println("\n========== RESULT ==========");
        System.out.println("[+] Active: " + active.size());
        System.out.println("[+] Saved: " + OUTPUT_FILE);
        System.out.println("============================");
    }
}
