import SwiftUI
import AppKit

struct Plugin: Codable, Identifiable { var name: String; var version: String; var enabled: Bool; var id: String { name } }
struct Health: Codable {
    var state: String; var checkedAt: Double?; var content: Int?; var learning: Int?; var configuration: Int?; var workspace: Int?
    var staged: Int?; var unstaged: Int?; var untracked: Int?; var conflicts: Int?; var ahead: Int?; var behind: Int?
    var branch: String?; var repository: String?; var nested: Bool?; var commitTime: Double?; var commit: String?; var commitSubject: String?
    var lastEdit: Double?; var editPartial: Bool?; var filesSampled: Int?; var upstream: String?; var error: String?; var plugins: [Plugin]
    var label: String {
        switch state { case "clean": return "Committed"; case "dirty":
            if (content ?? 0)+(learning ?? 0)==0 { return (configuration ?? 0)>0 ? "Settings changes" : "Workspace changes" }
            return "Uncommitted changes"; case "conflict": return "Merge conflict"; case "missing": return "Unavailable"; case "noGit": return "Not using Git"; case "error": return "Check failed"; default: return "Not checked" }
    }
    var color: Color { switch state { case "clean": return .mint; case "dirty": return .orange; case "conflict","error": return .red; default: return .secondary } }
}
struct Vault: Codable, Identifiable {
    var id: String; var path: String; var title: String; var groups: [String]; var favorite: Bool; var description: String; var cover: String; var aliases: [String]; var available: Bool; var status: Health?
    var tint: Color { switch groups.first ?? "" { case "Research": return Color(red:0.48,green:0.57,blue:1); case "Mechanical Engineering": return .orange; case "Physics": return .cyan; case "Mathematics": return .purple; case "Courses": return .yellow; case "Chemistry": return .mint; case "Computer Science": return .orange; default: return .pink } }
    var symbol: String { switch groups.first ?? "" { case "Research": return "sparkle.magnifyingglass"; case "Mechanical Engineering": return "gearshape.2"; case "Physics": return "atom"; case "Mathematics": return "function"; case "Courses": return "graduationcap"; case "Chemistry": return "flask"; case "Computer Science": return "chevron.left.forwardslash.chevron.right"; default: return "books.vertical" } }
}
struct Snapshot: Codable { var vaults: [Vault]; var revision: Int; var registryRevision: String }

@MainActor final class Library: ObservableObject {
    @Published var snapshot = Snapshot(vaults: [], revision: 0, registryRevision: "")
    @Published var busy = false
    @Published var error: String?
    @Published var query = ""
    @Published var section = "All vaults"
    @Published var selected: String?
    @Published var editing: Vault?
    @Published var shortcutVault: Vault?
    var groups: [String] {
        Array(Set(snapshot.vaults.flatMap(\.groups))).sorted {
            let a = $0 == "Research" ? 0 : ($0 == "Other" ? 2 : 1)
            let b = $1 == "Research" ? 0 : ($1 == "Other" ? 2 : 1)
            return a == b ? $0.localizedStandardCompare($1) == .orderedAscending : a < b
        }
    }
    var filtered: [Vault] { snapshot.vaults.filter { v in
        let inSection = section == "All vaults" || (section == "Favorites" && v.favorite) || (section == "Unavailable" && !v.available) || v.groups.contains(section)
        let text = ([v.title,v.path,v.description] + v.aliases + v.groups).joined(separator: " ")
        return inSection && (query.isEmpty || text.localizedCaseInsensitiveContains(query))
    }.sorted { $0.title.localizedStandardCompare($1.title) == .orderedAscending } }
    func call(_ action: String, input: [String:Any] = [:], completion: @escaping (Result<Snapshot,Error>) -> Void) {
        let data = try? JSONSerialization.data(withJSONObject: input)
        let python = Bundle.main.object(forInfoDictionaryKey: "VMPython") as? String ?? "/opt/homebrew/bin/python3"
        let script = Bundle.main.resourceURL!.appendingPathComponent("backend.py").path
        DispatchQueue.global(qos:.utility).async {
            do {
                let p=Process(); p.executableURL=URL(fileURLWithPath:python); p.arguments=[script,action]
                let output=Pipe(), err=Pipe(), stdin=Pipe(); p.standardOutput=output; p.standardError=err; p.standardInput=stdin
                try p.run(); if let data=data { stdin.fileHandleForWriting.write(data) }; try? stdin.fileHandleForWriting.close()
                let bytes=output.fileHandleForReading.readDataToEndOfFile(); p.waitUntilExit()
                if p.terminationStatus != 0 {
                    let obj=(try? JSONSerialization.jsonObject(with:bytes)) as? [String:Any]
                    throw NSError(domain:"VaultManager",code:1,userInfo:[NSLocalizedDescriptionKey:obj?["error"] as? String ?? "The inspection helper failed."])
                }
                let value=try JSONDecoder().decode(Snapshot.self,from:bytes)
                DispatchQueue.main.async { completion(.success(value)) }
            } catch { DispatchQueue.main.async { completion(.failure(error)) } }
        }
    }
    func load(scan: Bool = false) {
        if busy { return }; busy=true
        call(scan ? "scan" : "discover") { result in
            self.busy=false
            switch result { case .success(let s): self.snapshot=s; case .failure(let e): self.error=e.localizedDescription }
        }
    }
    func save(_ v: Vault, extras: [String:Any] = [:]) {
        var input: [String:Any] = ["revision":snapshot.revision,"path":v.path,"title":v.title,"description":v.description,"groups":v.groups,"cover":v.cover,"favorite":v.favorite]
        input.merge(extras) { _,new in new }
        call("update", input:input) { result in
            switch result { case .success(let s): self.snapshot=s; self.editing=nil; case .failure(let e): self.error=e.localizedDescription }
        }
    }
    func favorite(_ v: Vault) { save(v,extras:["favorite":!v.favorite]) }
    func changeShortcut(_ v: Vault, old: String, name: String) {
        call("shortcut",input:["registryRevision":snapshot.registryRevision,"path":v.path,"old":old,"alias":name]) { result in
            switch result { case .success(let s): self.snapshot=s; self.shortcutVault=nil; case .failure(let e): self.error=e.localizedDescription }
        }
    }
    func add() {
        let panel=NSOpenPanel(); panel.canChooseDirectories=true; panel.canChooseFiles=false; panel.prompt="Add vault"; panel.message="Choose an existing Obsidian vault folder."
        if panel.runModal() == .OK, let url=panel.url {
            if let v=snapshot.vaults.first(where:{$0.path==url.path}) { selected=v.id; return }
            editing=Vault(id:"new",path:url.path,title:url.lastPathComponent.replacingOccurrences(of:"_",with:" ").capitalized,groups:["Other"],favorite:false,description:"",cover:"",aliases:[],available:true,status:nil)
        }
    }
    func open(_ v: Vault) {
        var c=URLComponents(); c.scheme="obsidian"; c.host="open"; c.queryItems=[URLQueryItem(name:"path",value:v.path)]
        if let url=c.url { NSWorkspace.shared.open(url) }
    }
    func reveal(_ v: Vault) { NSWorkspace.shared.selectFile(nil,inFileViewerRootedAtPath:v.path) }
    func copy(_ text: String) { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(text,forType:.string) }
}

let page = Color(red:0.045,green:0.06,blue:0.095)
let panelColor = Color(red:0.075,green:0.095,blue:0.14)
func when(_ timestamp: Double?) -> String {
    guard let t=timestamp,t>0 else { return "Not available" }
    let f=DateFormatter(); f.dateStyle = .medium; f.timeStyle = .short
    return f.string(from:Date(timeIntervalSince1970:t))
}

struct Artwork: View {
    let v: Vault
    var body: some View {
        GeometryReader { g in
            ZStack {
                LinearGradient(colors:[v.tint.opacity(0.28),panelColor],startPoint:.topLeading,endPoint:.bottomTrailing)
                if !v.cover.isEmpty,let img=NSImage(contentsOfFile:v.cover) {
                    Image(nsImage:img).resizable().scaledToFill().frame(width:g.size.width,height:g.size.height).clipped()
                } else {
                    Canvas { context,size in
                        for n in 0..<13 {
                            var p=Path(); let r=CGFloat(n)*10+30
                            p.addEllipse(in:CGRect(x:size.width*0.64-r,y:size.height*0.47-r*0.45,width:r*2,height:r*0.9))
                            context.stroke(p,with:.color(v.tint.opacity(0.12+Double(n)*0.018)),lineWidth:1)
                        }
                    }.rotationEffect(.degrees(-25))
                    Image(systemName:v.symbol).font(.system(size:37,weight:.light)).foregroundStyle(v.tint.opacity(0.9)).frame(maxWidth:.infinity,maxHeight:.infinity,alignment:.leading).padding(.leading,25)
                }
            }
        }
    }
}
struct StatusPill: View {
    let h: Health?
    var body: some View { HStack(spacing:6) { Circle().fill(h?.color ?? .gray).frame(width:6,height:6); Text(h?.label ?? "Not checked").font(.system(size:11,weight:.medium)) }.foregroundStyle(h?.color ?? .secondary) }
}
struct VaultCard: View {
    let v: Vault; @ObservedObject var model: Library
    var body: some View {
        VStack(alignment:.leading,spacing:0) {
            ZStack(alignment:.topTrailing) {
                Artwork(v:v).frame(height:112).clipped()
                Button { model.favorite(v) } label: { Image(systemName:v.favorite ? "star.fill":"star").foregroundStyle(v.favorite ? .yellow:.white.opacity(0.65)).padding(10).background(.black.opacity(0.2),in:Circle()) }.buttonStyle(.plain).padding(10).help(v.favorite ? "Remove favorite":"Add favorite").accessibilityLabel("Favorite \(v.title)")
            }
            VStack(alignment:.leading,spacing:9) {
                Text(v.title).font(.system(size:17,weight:.semibold)).lineLimit(1)
                Text(v.description.isEmpty ? v.groups.joined(separator:" · ") : v.description).font(.system(size:12)).foregroundStyle(.secondary).lineLimit(1)
                HStack { StatusPill(h:v.status); Spacer(minLength:3); if let n=v.status?.ahead,n>0 { Label("\(n)",systemImage:"arrow.up").font(.caption).foregroundStyle(.blue).help("Commits awaiting push") } }
                Text(v.aliases.first.map { "oo \($0)" } ?? "No shortcut yet").font(.system(size:11,design:.monospaced)).foregroundStyle(.secondary).padding(.top,3)
            }.padding(17)
        }.background(panelColor).clipShape(RoundedRectangle(cornerRadius:16)).overlay(RoundedRectangle(cornerRadius:16).stroke(.white.opacity(0.07),lineWidth:1))
        .contentShape(RoundedRectangle(cornerRadius:16)).onTapGesture { model.selected=v.id }
        .accessibilityElement(children:.contain).accessibilityLabel(v.title)
        .contextMenu {
            Button("View vault") { model.selected=v.id }
            Button("Open in Obsidian") { model.open(v) }.disabled(!v.available)
            Button("Reveal in Finder") { model.reveal(v) }.disabled(!v.available)
            Button("Copy path") { model.copy(v.path) }
            Button(v.favorite ? "Remove favorite":"Add favorite") { model.favorite(v) }
            Button("Edit details") { model.editing=v }
        }
    }
}
struct Gallery: View {
    @ObservedObject var model: Library
    let columns=[GridItem(.adaptive(minimum:255,maximum:390),spacing:20)]
    func group(_ name: String,_ items: [Vault]) -> some View {
        VStack(alignment:.leading,spacing:15) {
            HStack { Text(name).font(.system(size:19,weight:.semibold)); Text("\(items.count)").foregroundStyle(.secondary).font(.caption); Spacer() }
            LazyVGrid(columns:columns,spacing:20) { ForEach(items) { VaultCard(v:$0,model:model) } }
        }.padding(.bottom,22)
    }
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:12) {
                Text("YOUR KNOWLEDGE, IN ONE PLACE").font(.system(size:10,weight:.bold)).tracking(2.2).foregroundStyle(.cyan.opacity(0.75))
                HStack(alignment:.firstTextBaseline) { Text(model.section == "All vaults" ? "The vault gallery" : model.section).font(.system(size:33,weight:.bold)); Spacer(); Text("\(model.filtered.count) vaults").foregroundStyle(.secondary) }
                Text("A home for your research, ideas, and everything you’re learning.").foregroundStyle(.secondary).padding(.bottom,24)
                if model.filtered.isEmpty { ContentUnavailableView("No matching vaults",systemImage:"magnifyingglass",description:Text("Try a different search or add an existing vault.")) }
                if model.section == "All vaults" && model.query.isEmpty {
                    let favorites=model.filtered.filter(\.favorite)
                    if !favorites.isEmpty { group("Favorites",favorites) }
                    ForEach(model.groups,id:\.self) { name in
                        let items=model.filtered.filter { !$0.favorite && $0.groups.contains(name) }
                        if !items.isEmpty { group(name,items) }
                    }
                } else { group(model.query.isEmpty ? "Collection":"Search results",model.filtered) }
                Text("Git checks are local. Upstream counts use the last fetched refs; colors do not establish which Mac owns a vault.").font(.caption).foregroundStyle(.secondary).padding(.top,12)
            }.padding(30)
        }
    }
}
struct Metric: View {
    let title: String; let value: String; let detail: String
    var body: some View { VStack(alignment:.leading,spacing:10) { Text(title.uppercased()).font(.system(size:10,weight:.bold)).tracking(1.4).foregroundStyle(.secondary); Text(value).font(.system(size:17,weight:.semibold)); Text(detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true) }.frame(maxWidth:.infinity,alignment:.topLeading).padding(20).background(panelColor,in:RoundedRectangle(cornerRadius:13)) }
}
struct VaultDetail: View {
    let v: Vault; @ObservedObject var model: Library
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:23) {
                Button { model.selected=nil } label: { Label("Back to gallery",systemImage:"arrow.left") }.buttonStyle(.plain).foregroundStyle(.secondary)
                Artwork(v:v).frame(height:170).clipShape(RoundedRectangle(cornerRadius:18))
                HStack(alignment:.top) {
                    VStack(alignment:.leading,spacing:10) { Text(v.groups.joined(separator:" / ").uppercased()).font(.caption).tracking(1.5).foregroundStyle(v.tint); Text(v.title).font(.system(size:34,weight:.bold)); if !v.description.isEmpty { Text(v.description).foregroundStyle(.secondary) } }
                    Spacer()
                    Button { model.favorite(v) } label: { Image(systemName:v.favorite ? "star.fill":"star").foregroundStyle(.yellow) }.buttonStyle(.bordered)
                    Button("Edit details") { model.editing=v }.buttonStyle(.bordered)
                    Button("Open in Obsidian") { model.open(v) }.buttonStyle(.borderedProminent).disabled(!v.available)
                }
                HStack { Text(v.path).font(.system(size:12,design:.monospaced)).textSelection(.enabled).foregroundStyle(.secondary); Spacer(); Button("Finder") { model.reveal(v) }.disabled(!v.available); Button("Copy path") { model.copy(v.path) } }
                HStack { StatusPill(h:v.status); Spacer(); Text("Checked: \(when(v.status?.checkedAt))").font(.caption).foregroundStyle(.secondary) }
                if let h=v.status {
                    if let error=h.error { Text(error).foregroundStyle(.red) }
                    HStack(alignment:.top,spacing:14) {
                        Metric(title:"Latest vault commit",value:when(h.commitTime),detail:[h.commit,h.commitSubject].compactMap{$0}.joined(separator:" · "))
                        Metric(title:"Last content edit",value:when(h.lastEdit),detail:h.editPartial == true ? "Partial scan: newest observed timestamp. Some files were not inspected." : "File timestamps, including learning history. Excludes workspace and routine settings.")
                    }
                    HStack(alignment:.top,spacing:14) {
                        Metric(title:"Uncommitted",value:"\((h.staged ?? 0)+(h.untracked ?? 0)+(h.unstaged ?? 0)) change signals",detail:"\(h.content ?? 0) content · \(h.learning ?? 0) learning\n\(h.configuration ?? 0) settings · \(h.workspace ?? 0) workspace\n\(h.staged ?? 0) staged · \(h.unstaged ?? 0) unstaged · \(h.untracked ?? 0) untracked entries")
                        Metric(title:"Remote comparison",value:h.upstream == nil ? "No upstream" : "\(h.ahead ?? 0) ahead · \(h.behind ?? 0) behind",detail:"\(h.branch ?? "No branch")\nCached refs only; no fetch is performed."+(h.nested == true ? "\nBranch counts cover the parent repository.":""))
                    }
                    if h.nested == true { Text("Vault changes and latest commit are scoped to this folder. Repository: \(h.repository ?? "")").font(.caption).foregroundStyle(.secondary) }
                }
                VStack(alignment:.leading,spacing:14) {
                    HStack { Text("Terminal shortcuts").font(.title3.bold()); Spacer(); Button("Manage shortcut") { model.shortcutVault=v } }
                    Text(v.aliases.isEmpty ? "Add a memorable shortcut for this vault." : v.aliases.map{"oo \($0)"}.joined(separator:"   •   ")).font(.system(.body,design:.monospaced)).textSelection(.enabled)
                }.padding(20).background(panelColor,in:RoundedRectangle(cornerRadius:13))
                VStack(alignment:.leading,spacing:15) {
                    Text("Installed plugins").font(.title3.bold())
                    Text("Installed versions and enabled settings. This does not certify cross-plugin compatibility.").font(.caption).foregroundStyle(.secondary)
                    if let plugins=v.status?.plugins, !plugins.isEmpty {
                        ForEach(plugins.sorted{$0.name < $1.name}) { p in HStack { Circle().fill(p.enabled ? .mint:.gray).frame(width:6,height:6); Text(p.name); Spacer(); Text(p.version).font(.system(.caption,design:.monospaced)); Text(p.enabled ? "Enabled":"Disabled").foregroundStyle(.secondary).frame(width:65,alignment:.trailing) }; Divider() }
                    } else { Text("Refresh status to inspect this vault’s plugins.").foregroundStyle(.secondary) }
                }.padding(20).background(panelColor,in:RoundedRectangle(cornerRadius:13))
            }.padding(30)
        }
    }
}
struct EditSheet: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var model: Library
    @State var v: Vault
    @State var groups: String
    init(model:Library,v:Vault) { self.model=model; _v=State(initialValue:v); _groups=State(initialValue:v.groups.joined(separator:", ")) }
    var body: some View {
        VStack(alignment:.leading,spacing:18) {
            Text("Make it your own").font(.title2.bold())
            Form {
                TextField("Display name",text:$v.title)
                TextField("Area",text:$groups)
                TextField("Description",text:$v.description,axis:.vertical).lineLimit(2...4)
                Toggle("Favorite",isOn:$v.favorite)
                HStack { Text(v.cover.isEmpty ? "Generated artwork":"Custom cover selected").foregroundStyle(.secondary); Spacer(); Button("Choose cover…") { let p=NSOpenPanel(); p.allowedContentTypes=[.png,.jpeg,.heic,.tiff]; if p.runModal() == .OK { v.cover=p.url?.path ?? "" } }; if !v.cover.isEmpty { Button("Reset") { v.cover="" } } }
            }.formStyle(.grouped)
            HStack { Text("Organization stays outside your vault.").font(.caption).foregroundStyle(.secondary); Spacer(); Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction); Button("Save") { v.groups=[groups.trimmingCharacters(in:.whitespacesAndNewlines)]; model.save(v) }.keyboardShortcut(.defaultAction).buttonStyle(.borderedProminent) }
        }.padding(24).frame(width:580)
    }
}
struct ShortcutSheet: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var model: Library; let v: Vault
    @State var old=""; @State var name=""
    var body: some View {
        VStack(alignment:.leading,spacing:20) {
            Text("Terminal shortcut").font(.title2.bold())
            Text("Rename a shortcut or add another. The vault folder and note links stay in place.").foregroundStyle(.secondary)
            Picker("Existing shortcut",selection:$old) { Text("Add a new shortcut").tag(""); ForEach(v.aliases,id:\.self) { Text($0).tag($0) } }.onChange(of:old) { _,new in name=new }
            TextField("For example: fluids",text:$name)
            Text("oo \(name.isEmpty ? "shortcut":name)").font(.system(.title3,design:.monospaced)).foregroundStyle(.cyan)
            HStack { Spacer(); Button("Cancel") { dismiss() }; Button("Save shortcut") { model.changeShortcut(v,old:old,name:name) }.buttonStyle(.borderedProminent).disabled(name.isEmpty) }
        }.padding(26).frame(width:500)
    }
}
struct RootView: View {
    @StateObject var model=Library()
    var body: some View {
        HStack(spacing:0) {
            VStack(alignment:.leading,spacing:6) {
                HStack { Image(systemName:"square.stack.3d.up.fill").foregroundStyle(.cyan); Text("VAULT MANAGER").font(.system(size:12,weight:.bold)).tracking(1) }.padding(.bottom,30).padding(.top,12)
                side("All vaults","square.grid.2x2")
                side("Favorites","star")
                Text("AREAS").font(.system(size:10,weight:.bold)).tracking(1.5).foregroundStyle(.secondary).padding(.top,25).padding(.bottom,8)
                ForEach(model.groups,id:\.self) { side($0,"folder") }
                Spacer()
                side("Unavailable","externaldrive.badge.exclamationmark")
                Button { model.add() } label: { Label("Add existing vault",systemImage:"plus").frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,10) }.buttonStyle(.plain).foregroundStyle(.cyan)
                Text("LOCAL LIBRARY\nFiles stay where they belong.").font(.system(size:10)).foregroundStyle(.secondary).lineSpacing(4).padding(.top,12)
            }.padding(22).frame(width:225).background(panelColor.opacity(0.65))
            Divider()
            VStack(spacing:0) {
                HStack {
                    Image(systemName:"magnifyingglass").foregroundStyle(.secondary)
                    TextField("Search vaults, shortcuts, and areas",text:$model.query).textFieldStyle(.plain).onChange(of:model.query) { _,_ in model.selected=nil }.accessibilityLabel("Search vaults")
                    if !model.query.isEmpty { Button { model.query="" } label: { Image(systemName:"xmark.circle.fill") }.buttonStyle(.plain) }
                    Spacer()
                    if model.busy { ProgressView().controlSize(.small); Text("Checking…").font(.caption).foregroundStyle(.secondary) }
                    Button { model.load(scan:true) } label: { Label("Refresh status",systemImage:"arrow.clockwise") }.disabled(model.busy).help("Inspect files and Git locally; never fetch or commit")
                }.padding(.horizontal,30).padding(.vertical,18)
                Divider()
                if let id=model.selected,let v=model.snapshot.vaults.first(where:{$0.id==id}) { VaultDetail(v:v,model:model) } else { Gallery(model:model) }
            }
        }.background(page).preferredColorScheme(.dark).frame(minWidth:950,minHeight:650)
        .sheet(item:$model.editing) { EditSheet(model:model,v:$0) }
        .sheet(item:$model.shortcutVault) { ShortcutSheet(model:model,v:$0) }
        .alert("Couldn’t complete that action",isPresented:Binding(get:{model.error != nil},set:{if !$0 {model.error=nil}})) { Button("OK") { model.error=nil } } message: { Text(model.error ?? "") }
        .onAppear { model.load(); DispatchQueue.main.asyncAfter(deadline:.now()+1) { model.load(scan:true) } }
    }
    func side(_ title:String,_ icon:String) -> some View {
        Button { model.section=title; model.selected=nil; model.query="" } label: { HStack { Image(systemName:icon).frame(width:19); Text(title).font(.system(size:13,weight:model.section==title ? .semibold:.regular)); Spacer(); let n=model.snapshot.vaults.filter { title == "All vaults" || (title == "Favorites" && $0.favorite) || (title == "Unavailable" && !$0.available) || $0.groups.contains(title) }.count; Text("\(n)").font(.caption).foregroundStyle(.secondary) }.padding(.horizontal,10).padding(.vertical,10).background(model.section==title ? Color.white.opacity(0.07):.clear,in:RoundedRectangle(cornerRadius:8)) }.buttonStyle(.plain)
    }
}
@main struct VaultManagerApp: App {
    var body: some Scene { Window("Vault Manager",id:"main") { RootView() }.defaultSize(width:1220,height:850).commands { CommandGroup(replacing:.newItem) {} } }
}
