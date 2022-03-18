#!/usr/bin/env ruby
PAGETITLE = "Active Members not participating in meetings" # Wvisible:meeting
$LOAD_PATH.unshift '/srv/whimsy/lib'

require 'whimsy/asf'
require 'wunderbar/bootstrap'
require 'date'
require 'json'
require 'wunderbar/jquery/stupidtable'
require_relative 'meeting-util'

# Find latest meeting and check if it's in the future yet
MEETINGS = ASF::SVN['Meetings']
cur_mtg_dir = MeetingUtil.get_latest(MEETINGS)
meeting = File.basename(cur_mtg_dir)
today = Date.today.strftime('%Y%m%d')

# look for recent activity if there is an upcoming meeting
if meeting > today
  proxies = Dir["#{cur_mtg_dir}/proxies-received/*"].
    map {|file| File.basename(file, '.*')}

  _tag,emeritus = ASF::SVN.getlisting('emeritus-requests-received')
  emeritus.map! {|file| File.basename(file, '.*')}

  current_status = lambda do |id|
    if emeritus.include? id
      'Emeritus request received'
    elsif proxies.include? id
      'Proxy received'
    else
      'No response'
    end
  end
else
  current_status = lambda {'No response'}
end

# separator / is added when link is generated
ROSTER = "/roster/committer"
if not ENV['QUERY_STRING'] or ENV['QUERY_STRING'].include? 'json'
  ENV['HTTP_ACCEPT'] = 'application/json' 
end

# Precompute matrix and dates from attendance
def get_attend_matrices(dir)
  attendance = MeetingUtil.get_attendance(dir)

  # extract and format dates
  dates = attendance['dates'].sort.
  map {|date| Date.parse(date).strftime('%Y-%b')}

  # compute mappings of names to ids
  members = ASF::Member.list
  active = Hash[members.select {|_id, data| not data['status']}]
  nameMap = Hash[members.map {|id, data| [id, data[:name]]}]
  idMap = Hash[nameMap.to_a.map(&:reverse)]

  # analyze attendance
  matrix = attendance['matrix'].map do |name, meetings|
    id = idMap[name]
    next unless id and active[id]

    # exclude 'active entry'
    data = meetings.select {|key, value| key.start_with? '20'}.
      sort.reverse.map(&:last)

    first = data.length
    missed = (data.index {|datum| datum != '-'} || data.length)

    [id, name, first, missed]
  end
  return attendance, matrix, dates, nameMap
end

# produce HTML
_html do
  _body? do
    attendance, matrix, dates, nameMap = get_attend_matrices(MEETINGS)
    _whimsy_body(
      title: PAGETITLE,
      subtitle: 'Select A Date:',
      relatedtitle: 'Related Links',
      related: {
        'https://svn.apache.org/repos/private/foundation/Meetings/attend-report.txt' => 'Attendance Report',
        '/members/meeting' => 'Members Meeting How-To Guide',
        '/members/attendance-xcheck' => 'Members Meeting Attendance Crosscheck',
        '/members/inactive' => 'Inactive Member Feedback Form',
        '/members/proxy' => 'Members Meeting Proxy Assignment',
        '/members/subscriptions' => 'Members@ Mailing List Crosscheck'
      },
      helpblock: -> {
        _form_ do
          _span "List of members that have not participated, starting with the "
          _select name: 'meetingsMissed', onChange: 'this.form.submit()' do
            dates.reverse.each_with_index do |name, i|
              _option name, value: i+1, selected: (i+1 == @meetingsMissed.to_i)
            end
          end
          _span "meeting.  Active members does not include emeritus or deceased members. Includes data thru #{attendance['dates'].last} meeting."
        end
        _h4 'Definitions'
        _p do
          _ 'Participating is defined by doing at least one of the following:'
          _ul do
            _li 'Attending a members meeting in IRC'
            _li 'Voting in an election'
            _li 'Assigning a proxy'
          end
        end
      }
    ) do
    @meetingsMissed = (@meetingsMissed || 3).to_i
    count = 0
    _table.table.table_hover do
      _thead do
        _tr do
          _th 'Name', data_sort: 'string'
          _th 'Membership start date', data_sort: 'string'
          _th 'Last participated', data_sort: 'string'
          if meeting > today
            _th 'Current status', data_sort: 'string'
          end
        end
      end

      matrix.each do |id, _name, first, missed|
        next unless id

        if missed >= @meetingsMissed
          _tr_ do
            _td! {_a nameMap[id], href: "#{ROSTER}/#{id}"}
            _td dates[-first-1] || dates.first
            if missed >= first
              _td {_em 'never'}
            else
              _td dates[-missed-1]
            end

            if meeting > today
              _td current_status[id]
            end
          end
          count += 1
        end
      end
    end

    _div.count "Count: #{count} members inactive for #{@meetingsMissed} meetings:"

    summary = matrix.
      select {|id, _name, _first, missed| id && missed >= @meetingsMissed}.
      map(&:first).group_by {|id| current_status[id]}.sort

    _ul summary do |status, list|
      _li "#{status}: #{list.length}"
    end

    _script %{
      var table = $(".table").stupidtable();
      table.on("aftertablesort", function (event, data) {
        var th = $(this).find("th");
        th.find(".arrow").remove();
        var dir = $.fn.stupidtable.dir;
        var arrow = data.direction === dir.ASC ? "&uarr;" : "&darr;";
        th.eq(data.column).append('<span class="arrow">' + arrow +'</span>');
        });
      }
    end
  end
end

_json do
  meetingsMissed = (@meetingsMissed || 3).to_i
  _attendance, matrix, _dates, _nameMap = get_attend_matrices(MEETINGS)
  inactive = matrix.select do |id, _name, _first, missed|
    id and missed >= meetingsMissed
  end

  Hash[inactive.map {|id, name, _first, missed|
    [id, {name: name, missed: missed, status: current_status[id]}]
    }]
end